#!/usr/bin/env python
"""Append-only observation ledger for D11 prospective live-information capture.

EPISTEMIC STATUS: PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future
features cutoff-provable. Creates no historical evidence and repairs no historical gap.

Design, and the reason for each piece:

  * ``observations.jsonl`` is the ONLY authoritative file. It is opened in append mode and never
    rewritten. ``STATE_INDEX.json`` and ``WATERMARKS.json`` are DERIVED: deleting them and
    replaying the ledger must reproduce them exactly, which ``verify()`` and TESTS.py check.

  * ``first_seen_at_utc`` is set once per entity and copied onto every later record for that
    entity. Nothing in this module can change it. A revision APPENDS; it never overwrites.

  * A record is never backdated. ``observed_at_utc`` is a claim about when THIS repository saw
    the fact, so it is bounded above by the write moment and below by the last observation
    already recorded for the same source. A record that wants to describe an old fact records it
    in ``effective_at_utc`` -- which is a source assertion, never an observation claim, and never
    admits anything at a cutoff.

  * ``cutoff_basis`` is ``observed_at`` only when observation is provable. Otherwise it is
    ``CUTOFF_UNPROVEN`` and ``admissible_at()`` will never return the record. This encodes the
    program's S-TX lesson: a single retrospective scrape of a wire that carries real per-row
    effective dates still proves nothing about what was knowable at a historical cutoff.

  * Every path written is asserted to be inside this node's lane directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from capture_schema import (
    SCHEMA_ID,
    BackdateViolation,
    LedgerIntegrityError,
    SchemaViolation,
    ScopeViolation,
    canonical_json,
    entity_key as make_entity_key,
    now_utc,
    parse_utc,
    payload_digest,
    sha256_text,
    validate_payload,
)

LANE_DIR = Path(__file__).resolve().parent
LEDGER_FILE = "observations.jsonl"
STATE_FILE = "STATE_INDEX.json"
WATERMARK_FILE = "WATERMARKS.json"
MANIFEST_FILE = "MANIFEST.json"

CUTOFF_PROVABLE = "observed_at"
CUTOFF_UNPROVEN = "CUTOFF_UNPROVEN"

CHANGE_FIRST_SEEN = "first_seen"
CHANGE_CHANGE = "change"
CHANGE_REAFFIRMATION = "reaffirmation"

# Fields hashed into record_id -- i.e. everything except record_id itself.
_RECORD_FIELDS = [
    "schema", "ingest_seq", "ingest_at_utc", "domain", "source_id", "fetch_id", "entity_key",
    "observed_at_utc", "published_at_utc", "effective_at_utc", "cutoff_basis", "retrospective",
    "payload", "payload_digest", "prev_payload_digest", "change_kind", "change_index",
    "first_seen_at_utc", "revision_of",
]


def assert_in_scope(path: Path) -> Path:
    """Every write this node performs goes through here. Nothing outside the lane directory."""
    p = Path(path).resolve()
    try:
        p.relative_to(LANE_DIR)
    except ValueError:
        raise ScopeViolation(
            f"refusing to write {p}: outside this node's write scope {LANE_DIR}"
        ) from None
    return p


class SourceRegistry:
    """Declares, per source_id, whether its observation time is PROVABLE.

    ``observation_provable`` is true only for a source this repository fetches itself and
    timestamps at fetch. A source handed over as a bulk historical dump is not provable no
    matter how good its internal dates are.
    """

    def __init__(self, sources: dict[str, dict]):
        self.sources = dict(sources)

    def get(self, source_id: str) -> dict:
        if source_id not in self.sources:
            raise SchemaViolation(f"source_id {source_id!r} is not registered")
        return self.sources[source_id]

    def observation_provable(self, source_id: str) -> bool:
        return bool(self.get(source_id).get("observation_provable", False))


class CaptureLedger:
    def __init__(self, root, registry: SourceRegistry, clock=now_utc):
        self.root = assert_in_scope(Path(root))
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = assert_in_scope(self.root / LEDGER_FILE)
        self.registry = registry
        self._clock = clock
        self.entities: dict[str, dict] = {}
        self.watermarks: dict[str, str] = {}
        self.n_records = 0
        if self.path.exists():
            self._replay()

    # -- reading ------------------------------------------------------------------------------

    def read_records(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise LedgerIntegrityError(
                        f"{self.path}:{lineno} is not valid JSON: {exc}"
                    ) from None
        return out

    def _replay(self) -> None:
        self.entities, self.watermarks, self.n_records = self.rebuild_state(self.read_records())

    @staticmethod
    def rebuild_state(records: list[dict]) -> tuple[dict, dict, int]:
        """Derive the entity index and per-source watermarks from the ledger alone."""
        entities: dict[str, dict] = {}
        watermarks: dict[str, str] = {}
        for r in records:
            ek = r["entity_key"]
            ent = entities.get(ek)
            if ent is None:
                entities[ek] = {
                    "domain": r["domain"],
                    "entity_key": ek,
                    "first_seen_at_utc": r["first_seen_at_utc"],
                    "first_seen_record_id": r["record_id"],
                    "last_observed_at_utc": r["observed_at_utc"],
                    "last_record_id": r["record_id"],
                    "current_payload_digest": r["payload_digest"],
                    "current_payload": r["payload"],
                    "change_index": r["change_index"],
                    "n_observations": 1,
                    "n_changes": 0,
                    "n_reaffirmations": 0,
                    "cutoff_basis_seen": [r["cutoff_basis"]],
                    "sources_seen": [r["source_id"]],
                }
            else:
                ent["last_observed_at_utc"] = r["observed_at_utc"]
                ent["last_record_id"] = r["record_id"]
                ent["current_payload_digest"] = r["payload_digest"]
                ent["current_payload"] = r["payload"]
                ent["change_index"] = r["change_index"]
                ent["n_observations"] += 1
                if r["change_kind"] == CHANGE_CHANGE:
                    ent["n_changes"] += 1
                elif r["change_kind"] == CHANGE_REAFFIRMATION:
                    ent["n_reaffirmations"] += 1
                if r["cutoff_basis"] not in ent["cutoff_basis_seen"]:
                    ent["cutoff_basis_seen"].append(r["cutoff_basis"])
                if r["source_id"] not in ent["sources_seen"]:
                    ent["sources_seen"].append(r["source_id"])
            src = r["source_id"]
            if src not in watermarks or r["observed_at_utc"] > watermarks[src]:
                watermarks[src] = r["observed_at_utc"]
        return entities, watermarks, len(records)

    def history(self, entity_key: str) -> list[dict]:
        return [r for r in self.read_records() if r["entity_key"] == entity_key]

    # -- writing ------------------------------------------------------------------------------

    def append(
        self,
        domain: str,
        source_id: str,
        payload: dict,
        observed_at_utc: str,
        published_at_utc: str | None = None,
        effective_at_utc: str | None = None,
        retrospective: bool = False,
        fetch_id: str | None = None,
    ) -> dict:
        """Validate, then APPEND one observation. Never rewrites, never overwrites.

        Raises on every rejection; the caller sees a code, not a silent drop.
        """
        validate_payload(domain, payload)
        src = self.registry.get(source_id)

        ingest_at = self._clock()
        t_obs = parse_utc(observed_at_utc, "observed_at_utc")
        t_ing = parse_utc(ingest_at, "ingest_at_utc")

        # --- no-backdating rules -------------------------------------------------------------
        # B1: an observation cannot be claimed later than the moment it is written.
        if t_obs > t_ing:
            raise BackdateViolation(
                f"observed_at_utc {observed_at_utc} is after the write moment {ingest_at}",
                code="FUTURE_OBSERVATION",
            )
        # B2: per-source observation clock is non-decreasing. Once this repository has recorded
        #     that it saw source X at time T, it may not later claim an earlier sighting of X.
        wm = self.watermarks.get(source_id)
        if wm is not None and observed_at_utc < wm:
            raise BackdateViolation(
                f"observed_at_utc {observed_at_utc} precedes the recorded watermark {wm} "
                f"for source {source_id!r}",
                code="BACKDATED_OBSERVATION",
            )
        ek = make_entity_key(domain, payload)
        ent = self.entities.get(ek)
        # B3: cross-source guard -- no observation of an entity earlier than its own first sight.
        if ent is not None and observed_at_utc < ent["first_seen_at_utc"]:
            raise BackdateViolation(
                f"observed_at_utc {observed_at_utc} precedes first_seen_at_utc "
                f"{ent['first_seen_at_utc']} for entity {ek!r}",
                code="BACKDATED_ENTITY_OBSERVATION",
            )
        # B4: a retrospective bulk record may not claim an earlier observation than its own
        #     write moment, and can never be cutoff-provable. This is the S-TX lesson encoded:
        #     the transaction wire's per-row effective dates are real, and prove nothing about
        #     what was knowable before the single scrape that produced them.
        if retrospective and observed_at_utc != ingest_at:
            raise BackdateViolation(
                "a retrospective record must set observed_at_utc equal to its write moment "
                f"({ingest_at}); got {observed_at_utc}",
                code="RETROSPECTIVE_CLAIMS_EARLY_OBSERVATION",
            )
        # B5: publication cannot follow observation.
        if published_at_utc is not None:
            t_pub = parse_utc(published_at_utc, "published_at_utc")
            if t_pub > t_obs:
                raise BackdateViolation(
                    f"published_at_utc {published_at_utc} is after observed_at_utc "
                    f"{observed_at_utc}",
                    code="PUBLISHED_AFTER_OBSERVED",
                )
        # effective_at_utc is deliberately unconstrained in direction: a posted line or a
        # scheduled transaction legitimately takes effect in the future, and a wire record
        # legitimately took effect in the past. It is a SOURCE ASSERTION and never admits.
        if effective_at_utc is not None:
            parse_utc(effective_at_utc, "effective_at_utc")

        cutoff_basis = (
            CUTOFF_PROVABLE
            if (self.registry.observation_provable(source_id) and not retrospective)
            else CUTOFF_UNPROVEN
        )

        dig = payload_digest(payload)
        if ent is None:
            change_kind = CHANGE_FIRST_SEEN
            change_index = 0
            prev_dig = None
            revision_of = None
            first_seen = observed_at_utc
        else:
            prev_dig = ent["current_payload_digest"]
            revision_of = ent["last_record_id"]
            first_seen = ent["first_seen_at_utc"]  # immutable, copied forward
            if dig == prev_dig:
                change_kind = CHANGE_REAFFIRMATION
                change_index = ent["change_index"]
            else:
                change_kind = CHANGE_CHANGE
                change_index = ent["change_index"] + 1

        record = {
            "schema": SCHEMA_ID,
            "ingest_seq": self.n_records,
            "ingest_at_utc": ingest_at,
            "domain": domain,
            "source_id": source_id,
            "fetch_id": fetch_id,
            "entity_key": ek,
            "observed_at_utc": observed_at_utc,
            "published_at_utc": published_at_utc,
            "effective_at_utc": effective_at_utc,
            "cutoff_basis": cutoff_basis,
            "retrospective": bool(retrospective),
            "payload": payload,
            "payload_digest": dig,
            "prev_payload_digest": prev_dig,
            "change_kind": change_kind,
            "change_index": change_index,
            "first_seen_at_utc": first_seen,
            "revision_of": revision_of,
        }
        record["record_id"] = compute_record_id(record)

        line = canonical_json(record) + "\n"
        with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

        # update in-memory derived state by the same replay rule, so memory and file agree
        self.entities, self.watermarks, self.n_records = self.rebuild_state(self.read_records())
        _ = src  # registry entry consulted above; kept for readability
        return record

    # -- derived files ------------------------------------------------------------------------

    def write_derived(self) -> dict:
        records = self.read_records()
        entities, watermarks, n = self.rebuild_state(records)
        state = {
            "schema": "player_program/live_capture_state_index/1",
            "derived_from": LEDGER_FILE,
            "derived_not_maintained": (
                "Rebuildable by replaying observations.jsonl. If this file and the ledger "
                "disagree, the ledger governs and this file is regenerated."
            ),
            "n_records": n,
            "n_entities": len(entities),
            "entities": entities,
        }
        wm = {
            "schema": "player_program/live_capture_watermarks/1",
            "derived_from": LEDGER_FILE,
            "per_source_last_observed_at_utc": watermarks,
        }
        sp = assert_in_scope(self.root / STATE_FILE)
        wp = assert_in_scope(self.root / WATERMARK_FILE)
        sp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        wp.write_text(json.dumps(wm, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        ledger_bytes = self.path.read_bytes() if self.path.exists() else b""
        manifest = {
            "schema": "player_program/live_capture_manifest/1",
            "ledger_file": LEDGER_FILE,
            "ledger_sha256": sha256_text(ledger_bytes.decode("utf-8")) if ledger_bytes else None,
            "ledger_bytes": len(ledger_bytes),
            "n_records": n,
            "n_entities": len(entities),
            "domains_present": sorted({r["domain"] for r in records}),
            "sources_present": sorted({r["source_id"] for r in records}),
            "derived_not_maintained": (
                "A pure function of observations.jsonl. It carries no generation timestamp on "
                "purpose: a derived file that changes when nothing changed cannot be hash-pinned."
            ),
        }
        mp = assert_in_scope(self.root / MANIFEST_FILE)
        mp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest

    # -- integrity ----------------------------------------------------------------------------

    def verify(self) -> dict:
        """Re-derive every invariant from the bytes on disk. Returns a report; empty
        ``violations`` means the ledger is internally consistent."""
        records = self.read_records()
        violations: list[dict] = []

        def bad(code, detail, seq=None):
            violations.append({"code": code, "detail": detail, "ingest_seq": seq})

        first_seen: dict[str, str] = {}
        last_digest: dict[str, str] = {}
        last_record: dict[str, str] = {}
        change_idx: dict[str, int] = {}
        wm: dict[str, str] = {}

        for i, r in enumerate(records):
            if r.get("ingest_seq") != i:
                bad("INGEST_SEQ_NOT_CONTIGUOUS", f"expected {i}, got {r.get('ingest_seq')}", i)
            if compute_record_id(r) != r.get("record_id"):
                bad("RECORD_ID_MISMATCH", "record_id does not rederive from record content", i)
            try:
                t_obs = parse_utc(r["observed_at_utc"], "observed_at_utc")
                t_ing = parse_utc(r["ingest_at_utc"], "ingest_at_utc")
            except SchemaViolation as exc:
                bad("BAD_TIMESTAMP", str(exc), i)
                continue
            if t_obs > t_ing:
                bad("FUTURE_OBSERVATION", "observed_at_utc after ingest_at_utc", i)
            src = r["source_id"]
            if src in wm and r["observed_at_utc"] < wm[src]:
                bad("BACKDATED_OBSERVATION",
                    f"source {src}: {r['observed_at_utc']} < watermark {wm[src]}", i)
            wm[src] = max(wm.get(src, ""), r["observed_at_utc"])

            if r.get("retrospective") and r["cutoff_basis"] != CUTOFF_UNPROVEN:
                bad("RETROSPECTIVE_CLAIMED_PROVABLE", "retrospective record is not "
                    "CUTOFF_UNPROVEN", i)
            if r["cutoff_basis"] not in (CUTOFF_PROVABLE, CUTOFF_UNPROVEN):
                bad("BAD_CUTOFF_BASIS", str(r["cutoff_basis"]), i)
            if payload_digest(r["payload"]) != r["payload_digest"]:
                bad("PAYLOAD_DIGEST_MISMATCH", "payload_digest does not rederive", i)
            try:
                if make_entity_key(r["domain"], r["payload"]) != r["entity_key"]:
                    bad("ENTITY_KEY_MISMATCH", "entity_key does not rederive from payload", i)
            except SchemaViolation as exc:
                bad("ENTITY_KEY_UNDERIVABLE", str(exc), i)

            ek = r["entity_key"]
            if ek not in first_seen:
                first_seen[ek] = r["first_seen_at_utc"]
                if r["first_seen_at_utc"] != r["observed_at_utc"]:
                    bad("FIRST_SEEN_NOT_FIRST_OBSERVATION",
                        f"{ek}: first record has first_seen {r['first_seen_at_utc']} != "
                        f"observed {r['observed_at_utc']}", i)
                if r["change_kind"] != CHANGE_FIRST_SEEN:
                    bad("FIRST_RECORD_NOT_FIRST_SEEN", ek, i)
                if r["change_index"] != 0:
                    bad("FIRST_RECORD_CHANGE_INDEX_NOT_ZERO", ek, i)
                if r["prev_payload_digest"] is not None or r["revision_of"] is not None:
                    bad("FIRST_RECORD_HAS_PREDECESSOR", ek, i)
                change_idx[ek] = 0
            else:
                if r["first_seen_at_utc"] != first_seen[ek]:
                    bad("FIRST_SEEN_MUTATED",
                        f"{ek}: {r['first_seen_at_utc']} != {first_seen[ek]}", i)
                if r["observed_at_utc"] < first_seen[ek]:
                    bad("BACKDATED_ENTITY_OBSERVATION", ek, i)
                if r["prev_payload_digest"] != last_digest[ek]:
                    bad("CHAIN_BROKEN", f"{ek}: prev_payload_digest does not match", i)
                if r["revision_of"] != last_record[ek]:
                    bad("REVISION_CHAIN_BROKEN", ek, i)
                changed = r["payload_digest"] != last_digest[ek]
                want_kind = CHANGE_CHANGE if changed else CHANGE_REAFFIRMATION
                if r["change_kind"] != want_kind:
                    bad("CHANGE_KIND_WRONG",
                        f"{ek}: {r['change_kind']} but payload {'changed' if changed else 'held'}",
                        i)
                want_idx = change_idx[ek] + 1 if changed else change_idx[ek]
                if r["change_index"] != want_idx:
                    bad("CHANGE_INDEX_WRONG", f"{ek}: {r['change_index']} != {want_idx}", i)
                change_idx[ek] = want_idx
            last_digest[ek] = r["payload_digest"]
            last_record[ek] = r["record_id"]

        return {
            "schema": "player_program/live_capture_verify/1",
            "ledger": str(self.path.relative_to(LANE_DIR)),
            "n_records": len(records),
            "n_entities": len(first_seen),
            "violations": violations,
            "ok": not violations,
        }

    # -- cutoff admission ---------------------------------------------------------------------

    def admissible_at(self, cutoff_utc: str, domain: str | None = None) -> dict:
        """Latest state per entity that is PROVABLY observable strictly before ``cutoff_utc``.

        Strict inequality, per prediction_contract_v5 section 4: equality is a violation, not a
        pass. A CUTOFF_UNPROVEN record is never admitted regardless of its dates.
        """
        parse_utc(cutoff_utc, "cutoff_utc")
        out: dict[str, dict] = {}
        for r in self.read_records():
            if domain is not None and r["domain"] != domain:
                continue
            if r["cutoff_basis"] != CUTOFF_PROVABLE:
                continue
            if not (r["observed_at_utc"] < cutoff_utc):
                continue
            out[r["entity_key"]] = r
        return out


def compute_record_id(record: dict) -> str:
    core = {k: record.get(k) for k in _RECORD_FIELDS}
    return sha256_text(canonical_json(core))
