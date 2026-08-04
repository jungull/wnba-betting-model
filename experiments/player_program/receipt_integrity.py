#!/usr/bin/env python3
"""receipt_integrity.py — PERMANENT receipt-integrity gate for registered artifact families.

Born from the turnover receipt-drift defect: `canonical_player_events/1` was rebuilt under the
source-aware exact-duplicate policy (`source_aware_exact_duplicate/1`, 7 byte-identical legacy rows
dropped), `player_turnover_targets/1` was rebuilt on top of it, and **the validation receipt was
never regenerated**. For four hours the frozen, published receipt for a FROZEN AND VALID artifact
asserted 42,083 turnover events, 39,279 player-attributed and a 2,989/2,990 external
reconciliation with one named off-by-one disagreement, while the artifact on disk contained
42,082 / 39,278 and reconciled 2,990/2,990 exactly. Nothing in the program noticed. The receipt
still said `"verdict": "PASS"`, and it was that PASS — not the artifact — that downstream work read.

A receipt is a claim about a specific sequence of bytes. It certifies nothing once those bytes
change. `"verdict": "PASS"` next to a stale hash is worse than no receipt at all, because it
converts an unvalidated artifact into an apparently validated one.

THE SECOND, WORSE DEFECT -- a matching artifact manifest is INSUFFICIENT
------------------------------------------------------------------------
The repair established what had actually drifted, and it was not what the first version of this
module assumed. `TURNOVER_TARGET_RECEIPT.json` had NOT drifted: every artifact hash it recorded
matched the rebuilt parquets exactly. The file carrying the stale `PASS` was
`TURNOVER_VALIDATION.json`, written 11m55s BEFORE the rebuild, certifying the PRIOR artifact
hashes (`a360e5d8...` for the player parquet, `65447449...` for the team parquet).
`EVENT_VALIDATION.json` carried the analogous stale verdict. The repair regenerated validation
through the canonical paths; NO parquet byte was modified, then or by this module.

So a target receipt can agree with the artifact in every field while the PASS that certified it
predates those bytes or refers to different ones. That is a STALE VERDICT, and it is more
dangerous than a stale manifest, because a reader who sees a matching manifest and a PASS stops
looking. Checking artifact-vs-manifest alone would have cleared the very tree that was broken.

WHAT THIS MODULE VALIDATES -- the full chain, every link
--------------------------------------------------------
    contract -> producer -> artifact -> target receipt -> validation execution -> validation receipt

    contract              the version the artifact CARRIES in its own rows, the version each
                          receipt STATES, and the version registered here must all agree
    producer              the producer source hash pinned by every receipt == the source on disk
    artifact              the bytes on disk, hashed, are the subject of every other link
    target receipt        the producer receipt's manifest, its pinned upstream inputs, and every
                          count it records, each re-derived from the artifact bytes
    validation execution  the VALIDATOR source hash (a link distinct from the producer), the
                          validation timestamp strictly after artifact creation, the inputs the
                          validation run actually consumed (recomputed from those inputs, not
                          taken from the build's claim), and agreement between the two receipts
                          about which bytes exist at all
    validation receipt    the verdict, and whether the bytes that verdict certifies are the bytes
                          on disk now

Prefer hash and content evidence over mtime. `receipt_predates_artifact` is mtime-based and is
therefore weak immediately after a fresh `git checkout`, which rewrites every mtime. It is kept
as CORROBORATION only. The load-bearing staleness detectors are `stale_validation_verdict` and
`validation_precedes_artifact`, which compare hashes the receipt certifies against the current
bytes and timestamps the receipts RECORD IN THEIR OWN JSON -- both of which survive a checkout.

Call `audit_family(name)` or `sweep()` before trusting any registered artifact. Both return a
machine-readable audit and raise `ReceiptIntegrityFailure` on a blocking finding unless it is
explicitly adjudicated with a recorded reason.

Blocking finding kinds (22). The first 13 are `BLOCKING_V1`, frozen unchanged from the original
manifest layer; the last 9 are `BLOCKING_CHAIN`, the layer this extension adds:

    artifact_missing              a declared artifact file is not on disk
    receipt_missing               a declared receipt is not on disk
    receipt_unreadable            the receipt is not parseable JSON
    receipt_hash_absent           the receipt records no hash for a declared artifact
    artifact_hash_mismatch        recorded content hash != recomputed content hash
    input_hash_mismatch           a pinned upstream input has changed since the receipt was written
    count_divergence              a count recorded in the receipt != the count recomputed from the artifact
    count_unrecomputable          the recount raised; fail closed rather than skip the cross-check
    producer_sha_absent           the receipt pins no producer, so producer drift is undetectable
    producer_version_divergence   producer source hash differs from the hash in the receipt
    contract_version_divergence   schema / contract / parser version differs between artifact and receipt
    receipt_predates_artifact     mtime CORROBORATION: the artifact file is newer than the receipt
    validation_verdict_not_pass   the receipt records a verdict that is not PASS
    --- the chain layer ---
    stale_validation_verdict      A PASS THAT DOES NOT CERTIFY THE BYTES ON DISK. Either the
                                  hashes it certifies are not the current artifact hashes, or it
                                  was recorded before the artifact it certifies was built, or it
                                  names no bytes at all. THE DEFECT THAT ACTUALLY OCCURRED.
    validation_precedes_artifact  the recorded validation time is not strictly after the recorded
                                  artifact creation time
    validator_sha_absent          a validation receipt pins no validator source hash
    validator_version_divergence  the VALIDATOR source changed after the validation receipt was
                                  written (distinct from producer_version_divergence)
    validated_input_divergence    an input hash the validation receipt pins differs from the bytes
                                  on disk, or from the same input as pinned by the build
    input_witness_divergence      a value a receipt records ABOUT an upstream input, recomputed
                                  from that input's current bytes, disagrees. This binds counts
                                  that cannot be derived inside the family at all.
    receipt_hash_disagreement     two receipts in one family certify different bytes for the same
                                  artifact, so at most one of them describes the validation run
    validation_link_absent        the family declares a validator but registers no validation
                                  receipt, so nothing evidences that validation ever ran
    fresh_execution_not_proven    positive evidence that a receipt may have been copied forward
                                  rather than freshly executed. READ THE NAME LITERALLY: it says
                                  a fresh execution is not proven, NOT that validation did not
                                  happen. See "the undecidable case" below.

Non-blocking finding kinds:

    receipt_records_no_counts     the receipt carries no count this module knows how to recompute
    artifact_version_unbound      the artifact carries a version column no receipt records
    input_witness_unavailable     an upstream input needed to check a witness is not on disk
    validation_timeline_unbound   no receipt records a creation time to compare validation against
    gap_declaration_stale         a gap declared permanent below is no longer real; close it

Known, DECLARED gaps are reported separately in ``gaps`` -- they are structural limits of what
the receipts on disk make checkable, not findings about this tree. See ``known_gaps`` per family
and ``UNIVERSAL_GAPS``.

THE FIVE SHAPES THIS GATE MUST TELL APART (``CASES``; every relevant finding carries ``cases``)
-----------------------------------------------------------------------------------------------
    1  a current manifest paired with a stale PASS ....... stale_validation_verdict, with
       (the defect that actually occurred)                 target_receipt_current=True
    2  a current artifact paired with an old validator     validation_precedes_artifact, and
       run ................................................ stale_validation_verdict on timeline
    3  producer or validator changed AFTER the receipt .... producer_version_divergence /
                                                            validator_version_divergence
    4  a receipt copied forward without revalidation ...... fresh_execution_not_proven
    5  a regenerated artifact with unchanged stale
       validation metadata ................................ stale_validation_verdict carrying BOTH
                                                            hash and timeline evidence

THE UNDECIDABLE CASE (4) -- stated plainly
-------------------------------------------
Case 4 cannot be decided from what these receipts record. A validation receipt that is internally
consistent -- current artifact hashes, current producer and validator hashes, a plausible
timestamp -- is byte-for-byte what a genuine rerun would also have written. Nothing in it is
unique to one execution. So this module WILL NOT claim that no validation occurred. It reports
`fresh_execution_not_proven` only where there is POSITIVE evidence of duplication:

    * two receipts record the identical execution instant, to the microsecond, for what are
      claimed to be separate runs -- no two independent executions finish in the same instant;
    * a family declares a per-run identity token and two receipts carry the same value.

Everything else is reported as the declared gap `fresh_execution_unprovable`, not as a finding.
WHAT WOULD CLOSE IT: the validator emitting a per-execution nonce -- a uuid4 `run_id`, or a
monotonic counter -- into the receipt, so that a copy is detectable as a repeat; or an
append-only validation ledger keyed by (artifact_sha256, validator_sha256, run_id) that a copy
cannot extend; or a signature over that tuple; or the receipt recording the commit it was
produced at, which would let commit ancestry settle it. `git_lineage()` reconstructs ancestry
from the working tree's history as opt-in corroboration, but that is the repository's evidence,
not the receipt's, and it is silent on uncommitted or dirty paths.

Note the honest limit in the other direction too: a receipt copied forward when the artifact, the
producer, the validator, the contract and the inputs are ALL unchanged certifies exactly the
claim a rerun would have certified. The dangerous copies are the ones where something changed,
and every one of those trips a hash, count, witness or timeline check above.

Run::  python experiments/player_program/receipt_integrity.py
       python experiments/player_program/receipt_integrity.py --git-lineage
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np, pandas as pd                                                # noqa: E401,F401
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

#: the original manifest layer, frozen. Every kind in it is still blocking; the extension may
#: only ADD. `test_blocking_v1_is_still_wholly_blocking` holds this open.
BLOCKING_V1 = frozenset({
    "artifact_missing", "receipt_missing", "receipt_unreadable", "receipt_hash_absent",
    "artifact_hash_mismatch", "input_hash_mismatch", "count_divergence",
    "count_unrecomputable", "producer_sha_absent", "producer_version_divergence",
    "contract_version_divergence", "receipt_predates_artifact",
    "validation_verdict_not_pass"})

#: the chain layer: links the manifest layer never checked.
BLOCKING_CHAIN = frozenset({
    "stale_validation_verdict", "validation_precedes_artifact", "validator_sha_absent",
    "validator_version_divergence", "validated_input_divergence", "input_witness_divergence",
    "receipt_hash_disagreement", "validation_link_absent", "fresh_execution_not_proven"})

BLOCKING = set(BLOCKING_V1 | BLOCKING_CHAIN)

NON_BLOCKING = frozenset({
    "receipt_records_no_counts", "artifact_version_unbound", "input_witness_unavailable",
    "validation_timeline_unbound", "gap_declaration_stale"})

#: the chain this module validates, in order. Every finding is tagged with the link it broke.
CHAIN = ("contract", "producer", "artifact", "target_receipt", "validation_execution",
         "validation_receipt")

KIND_LINK = {
    "contract_version_divergence": "contract",
    "artifact_version_unbound": "contract",
    "producer_sha_absent": "producer",
    "producer_version_divergence": "producer",
    "artifact_missing": "artifact",
    "artifact_hash_mismatch": "artifact",
    "receipt_missing": "target_receipt",
    "receipt_unreadable": "target_receipt",
    "receipt_hash_absent": "target_receipt",
    "input_hash_mismatch": "target_receipt",
    "count_divergence": "target_receipt",
    "count_unrecomputable": "target_receipt",
    "receipt_records_no_counts": "target_receipt",
    "receipt_predates_artifact": "target_receipt",
    "receipt_hash_disagreement": "validation_execution",
    "validation_link_absent": "validation_execution",
    "validator_sha_absent": "validation_execution",
    "validator_version_divergence": "validation_execution",
    "validation_precedes_artifact": "validation_execution",
    "validated_input_divergence": "validation_execution",
    "input_witness_divergence": "validation_execution",
    "input_witness_unavailable": "validation_execution",
    "validation_timeline_unbound": "validation_execution",
    "fresh_execution_not_proven": "validation_execution",
    "gap_declaration_stale": "validation_execution",
    "validation_verdict_not_pass": "validation_receipt",
    "stale_validation_verdict": "validation_receipt",
}

#: the five failure shapes this gate is required to tell apart. Every finding that bears on one
#: carries the id in its ``cases`` list, so a caller can select on the shape and not only on the
#: kind. Case 4 is the one that is NOT decidable from what these receipts record; see the
#: docstring and ``fresh_execution_not_proven``.
CASES = {
    1: "current_manifest_with_stale_pass",
    2: "current_artifact_with_an_old_validator_run",
    3: "producer_or_validator_changed_after_the_receipt",
    4: "receipt_possibly_copied_forward_without_revalidation",
    5: "regenerated_artifact_with_unchanged_validation_metadata",
}

#: gaps that hold for EVERY family here, because no receipt in this program records the evidence.
UNIVERSAL_GAPS = (
    {"link": "validation_execution", "receipt": "*", "gap": "fresh_execution_unprovable",
     "probe": [("run_id",), ("execution_id",), ("nonce",), ("validation_run_id",)],
     "why": "no receipt records a per-execution identity emitted by the validator, so a receipt "
            "that is internally consistent cannot be distinguished from an identical rerun. "
            "This gate therefore never asserts that validation did not happen; it reports "
            "fresh_execution_not_proven only on positive evidence of duplication."},
    {"link": "validation_execution", "receipt": "*", "gap": "producing_commit_unrecorded",
     "probe": [("producing_commit",), ("commit",), ("git_commit",)],
     "why": "no receipt records the commit it was produced at, so commit ancestry cannot be "
            "checked from the receipt alone. `git_lineage()` reconstructs it from the working "
            "tree's history as opt-in corroboration; it is not evidence the receipt carries."},
)

#: a producer writes the artifact and then its receipt, so the receipt is always the later file.
#: the tolerance absorbs filesystem timestamp granularity only -- it is NOT a grace period for a
#: rebuild. A rebuild moves the content hash, and the hash check is what actually decides.
MTIME_TOLERANCE_S = 2.0

_MISSING = object()


class ReceiptIntegrityFailure(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(obj, path):
    """Resolve a JSON path. A ``check:<name>`` segment selects one record out of a checks list.

    Validation receipts in this program bury their counts inside ``checks[].detail``, keyed by the
    check name rather than by position. Positional indexing would silently bind to the wrong check
    the moment a validator gains or reorders a gate.
    """
    cur = obj
    for seg in path:
        if isinstance(seg, str) and seg.startswith("check:"):
            want = seg[len("check:"):]
            if not isinstance(cur, list):
                return _MISSING
            hit = [x for x in cur if isinstance(x, dict) and x.get("check") == want]
            if len(hit) != 1:
                return _MISSING
            cur = hit[0]
        elif isinstance(cur, dict):
            if seg not in cur:
                return _MISSING
            cur = cur[seg]
        elif isinstance(cur, list) and isinstance(seg, int):
            if seg >= len(cur):
                return _MISSING
            cur = cur[seg]
        else:
            return _MISSING
    return cur


def _distinct_column_values(path: Path, column: str) -> list:
    try:
        v = pd.read_parquet(path, columns=[column])[column]
    except Exception:                                                    # noqa: BLE001
        return []
    return sorted({str(x) for x in pd.unique(v)})


def parse_ts(v) -> datetime | None:
    """Parse a timestamp a receipt RECORDS IN ITS OWN JSON. Unlike an mtime this survives a
    `git checkout`, which is exactly why the staleness detectors are built on it."""
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo is not None else d.replace(tzinfo=timezone.utc)


def _first_recorded_ts(R: dict, paths) -> tuple[datetime | None, tuple | None]:
    for p in paths or ():
        d = parse_ts(resolve(R, p))
        if d is not None:
            return d, p
    return None, None


def _canon(x):
    """Compare receipt-recorded structures and recomputed ones on identical footing."""
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)) and float(x).is_integer():
        return int(x)
    return x


# --------------------------------------------------------------------------- #
# input witnesses -- what an upstream input SAYS ABOUT ITSELF, recomputed now
#
# A receipt frequently records a number that cannot be re-derived from its own family's artifact:
# TURNOVER_TARGET_RECEIPT.json records counts.turnover_events, which lives in the EVENTS artifact,
# and TURNOVER_VALIDATION.json records a whole census of the events file it read. Those numbers
# are the only content evidence of WHICH upstream bytes the build and the validation actually
# consumed. Recomputing them from the input on disk binds that edge without touching the input.
# --------------------------------------------------------------------------- #
_WITNESS_CACHE: dict[tuple, dict] = {}


def _dir_fingerprint(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.glob("*")):
        if f.is_file():
            st = f.stat()
            h.update(f"{f.name}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


def witness(name: str, path: Path, fn) -> dict:
    """Compute a witness once per distinct content fingerprint. Read-only, always."""
    key = (name, _dir_fingerprint(path) if path.is_dir() else sha256_file(path))
    if key not in _WITNESS_CACHE:
        _WITNESS_CACHE[key] = fn(path)
    return _WITNESS_CACHE[key]


def _w_events(p: Path) -> dict:
    E = pd.read_parquet(p, columns=["event_family", "event_uid", "source_system", "quality",
                                    "score_out_of_sequence"])
    fam = E["event_family"].astype(str)
    t = E[fam == "turnover"]
    tsrc = t["source_system"].astype(str)
    return {
        "canonical_rows": int(len(E)),
        "family_census": {str(k): int(v) for k, v in fam.value_counts().items()},
        "turnover_rows": int(len(t)),
        "turnover_unique_uids": int(t["event_uid"].nunique()),
        "turnover_rows_cdn": int((tsrc == "nba_cdn_playbyplay").sum()),
        "turnover_rows_legacy": int((tsrc == "nba_playbyplayv2").sum()),
        "turnover_degraded_rows": int((t["quality"].astype(str) == "degraded").sum()),
        "turnover_score_out_of_sequence_rows": int(t["score_out_of_sequence"].astype(bool).sum()),
    }


def _w_master_player(p: Path) -> dict:
    b = pd.read_parquet(p, columns=["minutes"])
    return {"box_rows": int(len(b)),
            "appeared_rows": int(b["minutes"].notna().sum()),
            "did_not_appear_rows": int(b["minutes"].isna().sum())}


def _w_master_team(p: Path) -> dict:
    t = pd.read_parquet(p, columns=["tov"])
    return {"rows": int(len(t)), "rows_with_tov": int(t["tov"].notna().sum())}


def _w_contract(p: Path) -> dict:
    c = pd.read_parquet(p, columns=["game_id"])
    return {"rows": int(len(c)), "games": int(c["game_id"].nunique())}


def _w_parquet_rows(p: Path) -> dict:
    return {"rows": int(pq.ParquetFile(p).metadata.num_rows)}


def _w_v15_prediction_hashes(d: Path) -> dict:
    """Re-derive the nested v15 pin exactly the way build_projected_exposure.py derived it:
    the sorted distinct values of the three hash columns, per prediction head."""
    cols = ("model_hash", "config_hash", "data_snapshot_hash")
    out: dict[str, dict] = {}
    for head in ("p_active", "e_minutes_given_active"):
        files = sorted(d.glob(f"predictions__{head}__*.parquet"))
        if not files:
            return {}
        df = pd.concat([pd.read_parquet(f, columns=list(cols)) for f in files],
                       ignore_index=True)
        out[head] = {k: sorted(df[k].dropna().unique().tolist()) for k in cols}
    return out


# --------------------------------------------------------------------------- #
# recounts -- recomputed from the artifact bytes, never from any receipt
# --------------------------------------------------------------------------- #
def _recount_turnover_targets(d: Path) -> dict[str, int]:
    P = pd.read_parquet(d / "player_turnover_targets_v1.parquet",
                        columns=["turnovers", "realised_off_possessions",
                                 "zero_possession_exposure", "rate_defined"])
    T = pd.read_parquet(d / "team_turnover_reconciliation_v1.parquet",
                        columns=["team_turnovers_total", "player_attributed",
                                 "team_unattributed", "diff_vs_external"])
    dv = T["diff_vs_external"]
    return {
        "player_game_rows": int(len(P)),
        "player_game_rows_with_zero_turnovers": int((P["turnovers"] == 0).sum()),
        "player_game_rows_with_turnovers": int((P["turnovers"] > 0).sum()),
        "player_turnovers_total": int(P["turnovers"].sum()),
        "team_game_rows": int(len(T)),
        "team_player_attributed": int(T["player_attributed"].sum()),
        "team_unattributed": int(T["team_unattributed"].sum()),
        "team_turnovers_total": int(T["team_turnovers_total"].sum()),
        "team_exact": int((dv == 0).sum()),
        "team_off_by_one": int((dv.abs() == 1).sum()),
        "team_larger": int((dv.abs() > 1).sum()),
        "player_rows_with_positive_exposure": int((P["realised_off_possessions"] > 0).sum()),
        "player_rows_zero_exposure": int(P["zero_possession_exposure"].sum()),
        "rate_defined_rows": int(P["rate_defined"].sum()),
    }


def _recount_event_contract(d: Path) -> dict[str, int]:
    f = d / "canonical_player_events_v1.parquet"
    E = pd.read_parquet(f, columns=["game_id", "event_family", "source_system", "quality",
                                    "taxonomy_from_text", "score_out_of_sequence",
                                    "source_file_sha256"])
    fam = E["event_family"].astype(str)
    src = E["source_system"].astype(str)
    return {
        "canonical_rows": int(pq.ParquetFile(f).metadata.num_rows),
        "universe_games": int(E["game_id"].nunique()),
        "source_file_sha256_count": int(E["source_file_sha256"].nunique()),
        "turnover_rows": int((fam == "turnover").sum()),
        "turnover_rows_cdn": int(((fam == "turnover") & (src == "nba_cdn_playbyplay")).sum()),
        "turnover_rows_legacy": int(((fam == "turnover") & (src == "nba_playbyplayv2")).sum()),
        "rebound_rows": int((fam == "rebound").sum()),
        "replay_rows": int((fam == "replay_or_administrative").sum()),
        "quality_ok_rows": int((E["quality"].astype(str) == "ok").sum()),
        "quality_degraded_rows": int((E["quality"].astype(str) == "degraded").sum()),
        "taxonomy_from_text_rows": int(E["taxonomy_from_text"].astype(bool).sum()),
        "score_out_of_sequence_rows": int(E["score_out_of_sequence"].astype(bool).sum()),
    }


def _recount_projected_exposure(d: Path) -> dict[str, int]:
    pace = pd.read_parquet(d / "team_possession_prior_v1.parquet", columns=["game_id"])
    return {
        "player_rows": int(pq.ParquetFile(d / "projected_player_possessions_v1.parquet")
                           .metadata.num_rows),
        "rotation_rows": int(pq.ParquetFile(d / "projected_team_rotations_v1.parquet")
                             .metadata.num_rows),
        "pace_rows": int(pq.ParquetFile(d / "team_possession_prior_v1.parquet").metadata.num_rows),
        "pace_games": int(pace["game_id"].nunique()),
    }


# --------------------------------------------------------------------------- #
# family specifications
# --------------------------------------------------------------------------- #
FAMILIES: dict[str, dict] = {
    "projected_exposure_v1": {
        "artifact_id": "projected_player_possessions/1",
        "dir": "projected_exposure_v1",
        "producer": "build_projected_exposure.py",
        "validator": "validate_projected_exposure.py",
        "artifacts": {
            "players": "projected_player_possessions_v1.parquet",
            "rotations": "projected_team_rotations_v1.parquet",
            "pace": "team_possession_prior_v1.parquet",
        },
        "recount": _recount_projected_exposure,
        "expected_versions": {"players": {"contract_version": "player_game_contract/5"}},
        "version_bindings": [],
        # the two scalar input paths are pinned by hash below. The v15 prediction pin is a NESTED
        # dict of hash LISTS, so it cannot be bound as a scalar -- it is bound as a witness,
        # re-derived from the prediction parquets the same way the producer derived it.
        "witnesses": {
            "contract_v5": {"anchor": "root", "fn": _w_contract,
                            "path": "experiments/prediction_contract_v5/"
                                    "player_game_enriched.parquet"},
            "v15": {"anchor": "root", "fn": _w_v15_prediction_hashes,
                    "path": "experiments/cbs_v15_player_oof_v5/attempt_001"},
        },
        "input_witnesses": [
            {"receipt": "PROJECTED_EXPOSURE_RECEIPT.json", "path": ("inputs", "contract_v5", "rows"),
             "witness": "contract_v5", "field": "rows"},
            {"receipt": "PROJECTED_EXPOSURE_RECEIPT.json", "path": ("universe", "contract_obligations"),
             "witness": "contract_v5", "field": "rows"},
            {"receipt": "PROJECTED_EXPOSURE_RECEIPT.json", "path": ("universe", "games"),
             "witness": "contract_v5", "field": "games"},
            {"receipt": "PROJECTED_EXPOSURE_RECEIPT.json",
             "path": ("inputs", "v15_predictions", "hashes"), "witness": "v15", "field": None},
            # what the VALIDATION run consumed: it re-read the contract itself
            {"receipt": "PROJECTED_EXPOSURE_VALIDATION.json",
             "path": ("checks", "check:grain_arithmetic_reconciles", "detail", "contract_44851",
                      "value"), "witness": "contract_v5", "field": "rows"},
        ],
        "known_gaps": [],
        "receipts": [
            {
                "file": "PROJECTED_EXPOSURE_RECEIPT.json",
                "role": "producer",
                "created_at": [("finished_utc",), ("generated_utc",)],
                "identity": {"schema": ("schema",),
                             "artifact_id": ("artifact_id",),
                             "pace_artifact_id": ("pace_artifact_id",)},
                "expect_identity": {"schema": "projected_exposure_receipt/1",
                                    "artifact_id": "projected_player_possessions/1",
                                    "pace_artifact_id": "team_possession_prior/1"},
                "hashes": {
                    "players": ("outputs", "projected_player_possessions_v1.parquet", "sha256"),
                    "rotations": ("outputs", "projected_team_rotations_v1.parquet", "sha256"),
                    "pace": ("outputs", "team_possession_prior_v1.parquet", "sha256"),
                },
                "producer_sha": ("producer", "sha256_after"),
                "inputs": {
                    ("inputs", "contract_v5", "sha256"):
                        "experiments/prediction_contract_v5/player_game_enriched.parquet",
                    ("inputs", "possessions", "sha256"):
                        "experiments/player_program/possessions_v2/possessions_raw_v2.parquet",
                },
                "counts": [
                    {"path": ("outputs", "projected_player_possessions_v1.parquet", "rows"),
                     "count": "player_rows"},
                    {"path": ("outputs", "projected_team_rotations_v1.parquet", "rows"),
                     "count": "rotation_rows"},
                    {"path": ("outputs", "team_possession_prior_v1.parquet", "rows"),
                     "count": "pace_rows"},
                    {"path": ("universe", "games"), "count": "pace_games"},
                ],
            },
            {
                "file": "PROJECTED_EXPOSURE_VALIDATION.json",
                "role": "validation",
                "validated_at": [("validated_utc",)],
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",)},
                "expect_identity": {"schema": "projected_exposure_validation/2",
                                    "artifact_id": "projected_player_possessions/1"},
                "hashes": {
                    "players": ("artifact_sha256", "projected_player_possessions_v1.parquet"),
                    "rotations": ("artifact_sha256", "projected_team_rotations_v1.parquet"),
                    "pace": ("artifact_sha256", "team_possession_prior_v1.parquet"),
                },
                "producer_sha": ("producer_sha256",),
                "validator_sha": ("validator_sha256",),
                "verdict": ("verdict",),
                "counts": [
                    {"path": ("checks", "check:home_away_accounting_reconciles", "detail",
                              "team_game_rows_total"), "count": "rotation_rows"},
                    {"path": ("checks", "check:pace_matches_independent_rederivation", "detail",
                              "team_games"), "count": "pace_rows"},
                    {"path": ("checks", "check:grain_arithmetic_reconciles", "detail", "games"),
                     "count": "pace_games"},
                    {"path": ("checks", "check:per_regime_reconciliation_closes", "detail",
                              "games"), "count": "pace_games"},
                ],
            },
        ],
    },
    "event_contract_v1": {
        "artifact_id": "canonical_player_events/1",
        "dir": "event_contract_v1",
        "producer": "build_canonical_events.py",
        "validator": "validate_canonical_events.py",
        "artifacts": {"events": "canonical_player_events_v1.parquet"},
        "recount": _recount_event_contract,
        "expected_versions": {"events": {"parser_version": "canonical_player_events/1",
                                         "contract_version": "player_event_contract/1"}},
        # the artifact CARRIES its own parser/contract version in every row; the receipt states
        # them separately. A producer that changes one without the other is exactly the drift.
        "version_bindings": [
            {"artifact": "events", "column": "parser_version",
             "receipt": "EVENT_NORMALISATION_RECEIPT.json", "path": ("parser_version",)},
            {"artifact": "events", "column": "contract_version",
             "receipt": "EVENT_NORMALISATION_RECEIPT.json", "path": ("contract_version",)},
        ],
        # this family pins NO upstream input by hash in either receipt -- the producer records
        # per-game source hashes inside the artifact instead. The input link is therefore carried
        # entirely by witnesses: numbers the receipts record ABOUT the game list and the
        # possessions artifact, re-derived here from those files' current bytes.
        "witnesses": {
            "contract_v5": {"anchor": "root", "fn": _w_contract,
                            "path": "experiments/prediction_contract_v5/"
                                    "player_game_enriched.parquet"},
            "possessions": {"anchor": "root", "fn": _w_parquet_rows,
                            "path": "experiments/player_program/possessions_v2/"
                                    "possessions_raw_v2.parquet"},
        },
        "input_witnesses": [
            {"receipt": "EVENT_NORMALISATION_RECEIPT.json", "path": ("universe_games",),
             "witness": "contract_v5", "field": "games"},
            # what the VALIDATION run consumed, recomputed from those inputs
            {"receipt": "EVENT_VALIDATION.json",
             "path": ("checks", "check:all_universe_games_accounted", "detail", "games"),
             "witness": "contract_v5", "field": "games"},
            {"receipt": "EVENT_VALIDATION.json",
             "path": ("checks", "check:no_information_from_outside_the_event_file", "detail",
                      "distinct_files_read"), "witness": "contract_v5", "field": "games"},
            {"receipt": "EVENT_VALIDATION.json",
             "path": ("checks", "check:structural_comparison_with_possessions", "detail",
                      "possession_rows"), "witness": "possessions", "field": "rows"},
            {"receipt": "EVENT_VALIDATION.json",
             "path": ("checks", "check:structural_comparison_with_possessions", "detail",
                      "games"), "witness": "contract_v5", "field": "games"},
        ],
        "known_gaps": [],
        "receipts": [
            {
                "file": "EVENT_NORMALISATION_RECEIPT.json",
                "role": "producer",
                "created_at": [("finished_utc",), ("generated_utc",)],
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",),
                             "experiment_id": ("experiment_id",)},
                "expect_identity": {"schema": "canonical_event_receipt/1",
                                    "artifact_id": "canonical_player_events/1",
                                    "experiment_id": "canonical_player_events_v1"},
                "hashes": {"events": ("artifact_sha256",)},
                "producer_sha": ("producer", "sha256_after"),
                "counts": [
                    {"path": ("canonical_rows",), "count": "canonical_rows"},
                    {"path": ("row_reconciliation", "canonical_total"), "count": "canonical_rows"},
                    {"path": ("universe_games",), "count": "universe_games"},
                    {"path": ("source_file_sha256_count",), "count": "source_file_sha256_count"},
                    {"path": ("quality_counts", "ok"), "count": "quality_ok_rows"},
                    {"path": ("quality_counts", "degraded"), "count": "quality_degraded_rows"},
                    {"path": ("taxonomy_from_text_rows",), "count": "taxonomy_from_text_rows"},
                    {"path": ("flag_counts", "taxonomy_from_text"),
                     "count": "taxonomy_from_text_rows"},
                    {"path": ("flag_counts", "score_out_of_sequence"),
                     "count": "score_out_of_sequence_rows"},
                    {"path": ("family_counts_by_source", "turnover", "nba_cdn_playbyplay"),
                     "count": "turnover_rows_cdn"},
                    {"path": ("family_counts_by_source", "turnover", "nba_playbyplayv2"),
                     "count": "turnover_rows_legacy"},
                ],
            },
            {
                "file": "EVENT_VALIDATION.json",
                "role": "validation",
                "validated_at": [("validated_utc",)],
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",)},
                "expect_identity": {"schema": "canonical_event_validation/1",
                                    "artifact_id": "canonical_player_events/1"},
                "hashes": {"events": ("artifact_sha256",)},
                "producer_sha": ("producer_sha256",),
                "validator_sha": ("validator_sha256",),
                "verdict": ("verdict",),
                "counts": [
                    {"path": ("checks", "check:all_universe_games_accounted", "detail", "events"),
                     "count": "canonical_rows"},
                    {"path": ("checks", "check:all_universe_games_accounted", "detail", "games"),
                     "count": "universe_games"},
                    {"path": ("checks", "check:canonical_keys_unique", "detail", "rows"),
                     "count": "canonical_rows"},
                    {"path": ("checks", "check:deterministic_rebuild", "detail", "rows_compared"),
                     "count": "canonical_rows"},
                    {"path": ("checks", "check:row_counts_reconcile_to_raw", "detail",
                              "canonical_total"), "count": "canonical_rows"},
                    {"path": ("checks", "check:structural_comparison_with_possessions", "detail",
                              "event_rows"), "count": "canonical_rows"},
                    {"path": ("checks", "check:no_future_information_used", "detail",
                              "rows_traceable_to_own_game_file"), "count": "canonical_rows"},
                    {"path": ("checks", "check:no_information_from_outside_the_event_file",
                              "detail", "event_files"), "count": "universe_games"},
                    {"path": ("checks", "check:taxonomy_covers_all_raw_values", "detail",
                              "rows_typed_from_description_text"),
                     "count": "taxonomy_from_text_rows"},
                ],
            },
        ],
    },
    "turnover_targets_v1": {
        "artifact_id": "player_turnover_targets/1",
        "dir": "turnover_targets_v1",
        "producer": "build_turnover_targets.py",
        "validator": "validate_turnover_targets.py",
        "artifacts": {"player": "player_turnover_targets_v1.parquet",
                      "team": "team_turnover_reconciliation_v1.parquet"},
        "recount": _recount_turnover_targets,
        "expected_versions": {},
        "version_bindings": [],
        # THE cross-family edge. `counts.turnover_events` and the whole event census recorded by
        # the validation receipt are derivable ONLY from the EVENTS artifact, so nothing inside
        # this family could ever have re-derived them. They are the content evidence of which
        # events bytes the build -- and separately the validation run -- actually consumed.
        "witnesses": {
            "events": {"anchor": "root", "fn": _w_events,
                       "path": "experiments/player_program/event_contract_v1/"
                               "canonical_player_events_v1.parquet"},
            "master_player": {"anchor": "root", "fn": _w_master_player,
                              "path": "data/masters/master_player.parquet"},
            "master_team": {"anchor": "root", "fn": _w_master_team,
                            "path": "data/masters/master_team.parquet"},
        },
        "input_witnesses": [
            # what the BUILD consumed
            {"receipt": "TURNOVER_TARGET_RECEIPT.json", "path": ("counts", "turnover_events"),
             "witness": "events", "field": "turnover_rows"},
            {"receipt": "TURNOVER_TARGET_RECEIPT.json",
             "path": ("by_source", "events", "nba_cdn_playbyplay"),
             "witness": "events", "field": "turnover_rows_cdn"},
            {"receipt": "TURNOVER_TARGET_RECEIPT.json",
             "path": ("by_source", "events", "nba_playbyplayv2"),
             "witness": "events", "field": "turnover_rows_legacy"},
            # what the VALIDATION RUN consumed -- validate_turnover_targets.py reads the events
            # artifact and master_player directly, and records these numbers about them
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:no_double_counting", "detail", "turnover_events"),
             "witness": "events", "field": "turnover_rows"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:no_double_counting", "detail", "unique_event_uids"),
             "witness": "events", "field": "turnover_unique_uids"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:no_double_counting", "detail", "degraded_turnover_rows"),
             "witness": "events", "field": "turnover_degraded_rows"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:no_double_counting", "detail",
                      "score_out_of_sequence_turnover_rows"),
             "witness": "events", "field": "turnover_score_out_of_sequence_rows"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:no_double_counting", "detail",
                      "families_present_in_events"),
             "witness": "events", "field": "family_census"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:one_disposition_per_event", "detail", "turnover_events"),
             "witness": "events", "field": "turnover_rows"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:universe_excludes_non_appearances", "detail", "box_rows"),
             "witness": "master_player", "field": "box_rows"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:universe_excludes_non_appearances", "detail",
                      "appeared_rows"), "witness": "master_player", "field": "appeared_rows"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:universe_excludes_non_appearances", "detail",
                      "excluded_did_not_appear"),
             "witness": "master_player", "field": "did_not_appear_rows"},
            {"receipt": "TURNOVER_VALIDATION.json",
             "path": ("checks", "check:external_team_reconciliation", "detail", "team_games"),
             "witness": "master_team", "field": "rows"},
        ],
        "known_gaps": [
            {"link": "validation_execution", "receipt": "TURNOVER_VALIDATION.json",
             "gap": "validator_not_pinned", "probe": ("validator_sha256",),
             "why": "validate_turnover_targets.py writes the PRODUCER sha256 into its receipt but "
                    "not its own, and no registry record pins it either, so nothing on disk "
                    "records which validator version produced this PASS. The other two families "
                    "pin theirs and are checked. Closing this needs one line in the validator; "
                    "this module must not, and does not, edit receipts to close it."},
        ],
        "receipts": [
            {
                "file": "TURNOVER_TARGET_RECEIPT.json",
                "role": "producer",
                "created_at": [("finished_utc",), ("generated_utc",)],
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",),
                             "experiment_id": ("experiment_id",)},
                "expect_identity": {"schema": "turnover_target_receipt/1",
                                    "artifact_id": "player_turnover_targets/1",
                                    "experiment_id": "turnover_target_contract_v1"},
                "hashes": {"player": ("artifact_sha256", "player"),
                           "team": ("artifact_sha256", "team")},
                "producer_sha": ("producer_sha256",),
                # the defect travelled along exactly this edge: the events artifact was rebuilt
                # under the dedup policy and this receipt kept pointing at the pre-dedup bytes.
                "inputs": {
                    ("inputs", "events"):
                        "experiments/player_program/event_contract_v1/"
                        "canonical_player_events_v1.parquet",
                    ("inputs", "possessions"):
                        "experiments/player_program/possessions_v2/possessions_raw_v2.parquet",
                    ("inputs", "master_player"): "data/masters/master_player.parquet",
                    ("inputs", "master_team"): "data/masters/master_team.parquet",
                },
                "counts": [
                    {"path": ("counts", "player_game_rows"), "count": "player_game_rows"},
                    {"path": ("counts", "player_game_rows_with_zero_turnovers"),
                     "count": "player_game_rows_with_zero_turnovers"},
                    {"path": ("counts", "team_game_rows"), "count": "team_game_rows"},
                    {"path": ("counts", "player_attributed"), "count": "team_player_attributed"},
                    {"path": ("counts", "team_unattributed"), "count": "team_unattributed"},
                    {"path": ("exposure", "player_rows_with_positive_exposure"),
                     "count": "player_rows_with_positive_exposure"},
                    {"path": ("exposure", "player_rows_zero_exposure"),
                     "count": "player_rows_zero_exposure"},
                    {"path": ("exposure", "rate_defined_rows"), "count": "rate_defined_rows"},
                    {"path": ("external_reconciliation_preview", "team_exact"),
                     "count": "team_exact"},
                    {"path": ("external_reconciliation_preview", "team_off_by_one"),
                     "count": "team_off_by_one"},
                    {"path": ("external_reconciliation_preview", "team_larger"),
                     "count": "team_larger"},
                ],
            },
            {
                "file": "TURNOVER_VALIDATION.json",
                "role": "validation",
                "validated_at": [("validated_utc",)],
                # declared absent, not forgotten: see known_gaps/validator_not_pinned above
                "validator_sha": None,
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",),
                             "experiment_id": ("experiment_id",)},
                "expect_identity": {"schema": "turnover_target_validation/1",
                                    "artifact_id": "player_turnover_targets/1",
                                    "experiment_id": "turnover_target_contract_v1"},
                "hashes": {"player": ("artifact_sha256", "player"),
                           "team": ("artifact_sha256", "team")},
                "producer_sha": ("producer_sha256",),
                "verdict": ("verdict",),
                "counts": [
                    {"path": ("checks", "check:mechanism_sums_to_player_total", "detail",
                              "player_rows"), "count": "player_game_rows"},
                    {"path": ("checks", "check:mechanism_sums_to_player_total", "detail",
                              "total_turnovers"), "count": "player_turnovers_total"},
                    {"path": ("checks", "check:mechanism_sums_to_player_total", "detail",
                              "total_from_mechanisms"), "count": "player_turnovers_total"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "team_games"), "count": "team_game_rows"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "player_attributed"), "count": "team_player_attributed"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "team_unattributed"), "count": "team_unattributed"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "team_total"), "count": "team_turnovers_total"},
                    {"path": ("checks", "check:no_duplicate_grain", "detail", "player_rows"),
                     "count": "player_game_rows"},
                    {"path": ("checks", "check:no_duplicate_grain", "detail", "team_rows"),
                     "count": "team_game_rows"},
                    {"path": ("checks", "check:zero_turnover_rows_retained", "detail",
                              "zero_turnover_rows"), "count": "player_game_rows_with_zero_turnovers"},
                    {"path": ("checks", "check:zero_turnover_rows_retained", "detail",
                              "nonzero_rows"), "count": "player_game_rows_with_turnovers"},
                    {"path": ("checks", "check:no_player_on_both_teams", "detail",
                              "players_with_turnovers"), "count": "player_game_rows_with_turnovers"},
                    {"path": ("checks", "check:universe_excludes_non_appearances", "detail",
                              "appeared_rows"), "count": "player_game_rows"},
                    {"path": ("checks", "check:exposure_coverage", "detail",
                              "rows_with_positive_exposure"),
                     "count": "player_rows_with_positive_exposure"},
                    {"path": ("checks", "check:exposure_coverage", "detail",
                              "rows_zero_reconstructed_exposure"),
                     "count": "player_rows_zero_exposure"},
                    {"path": ("checks", "check:exposure_coverage", "detail", "rate_defined_rows"),
                     "count": "rate_defined_rows"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail",
                              "team_games"), "count": "team_game_rows"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail", "exact"),
                     "count": "team_exact"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail",
                              "off_by_one"), "count": "team_off_by_one"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail", "larger"),
                     "count": "team_larger"},
                    {"path": ("checks", "check:external_player_reconciliation", "detail",
                              "rows_compared"), "count": "player_game_rows"},
                ],
            },
        ],
    },
}


# --------------------------------------------------------------------------- #
# adjudication
# --------------------------------------------------------------------------- #
def finding_key(f: dict) -> str:
    return "|".join([str(f.get("family", "-")), str(f.get("receipt", "-")),
                     str(f["kind"]), str(f.get("subject", "-"))])


def _adjudication_for(f: dict, adjudicated: dict) -> object:
    for k in (finding_key(f),
              f"{f.get('family', '-')}|{f.get('receipt', '-')}|{f['kind']}",
              f"{f.get('family', '-')}|{f['kind']}"):
        if adjudicated.get(k):
            return adjudicated[k]
    return None


def _gaps_for(spec: dict) -> list[dict]:
    return list(spec.get("known_gaps") or []) + list(UNIVERSAL_GAPS)


def _gap_declared(spec: dict, receipt: str, gap: str) -> bool:
    return any(g.get("gap") == gap and g.get("receipt") in ("*", receipt)
               for g in _gaps_for(spec))


# --------------------------------------------------------------------------- #
# commit ancestry -- OPT IN. This is the repository's evidence, not the receipt's.
# --------------------------------------------------------------------------- #
def _git(root: Path, *args: str) -> str | None:
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           timeout=30)
    except Exception:                                                    # noqa: BLE001
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_lineage(name: str, spec: dict | None = None, base: Path | None = None,
                root: Path | None = None) -> dict:
    """Reconstruct commit ancestry for one family: which commit last wrote each artifact and each
    receipt, whether the path is dirty, and whether each validation receipt's commit is a
    descendant of every artifact's commit.

    This is CORROBORATION and is never blocking. A dirty or untracked path yields no evidence,
    and a rewritten history yields the wrong evidence. The receipts record no producing commit of
    their own -- see UNIVERSAL_GAPS/producing_commit_unrecorded.
    """
    spec = spec or FAMILIES[name]
    base = Path(base) if base is not None else HERE
    root = Path(root) if root is not None else ROOT
    fdir = base / spec["dir"]
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    out: dict = {"family": name, "git_available": inside == "true", "paths": {}, "verdicts": []}
    if not out["git_available"]:
        return out

    def _one(p: Path) -> dict:
        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
        except ValueError:
            return {"tracked": False, "reason": "outside the repository"}
        tracked = bool(_git(root, "ls-files", "--error-unmatch", rel))
        if not tracked:
            return {"path": rel, "tracked": False}
        dirty = bool(_git(root, "status", "--porcelain", "--", rel))
        return {"path": rel, "tracked": True, "dirty": dirty,
                "last_commit": _git(root, "log", "-1", "--format=%H", "--", rel),
                "last_commit_utc": _git(root, "log", "-1", "--format=%cI", "--", rel)}

    for key, fname in spec["artifacts"].items():
        out["paths"][f"artifact:{key}"] = _one(fdir / fname)
    for r in spec["receipts"]:
        out["paths"][f"receipt:{r['file']}"] = _one(fdir / r["file"])

    art = [v for k, v in out["paths"].items()
           if k.startswith("artifact:") and v.get("last_commit") and not v.get("dirty")]
    for r in spec["receipts"]:
        if r.get("role") != "validation":
            continue
        v = out["paths"].get(f"receipt:{r['file']}", {})
        if not v.get("last_commit") or v.get("dirty"):
            out["verdicts"].append({"receipt": r["file"], "verdict": "no_evidence",
                                    "why": "the receipt is dirty or untracked"})
            continue
        for a in art:
            ok = _git(root, "merge-base", "--is-ancestor", a["last_commit"], v["last_commit"])
            out["verdicts"].append({
                "receipt": r["file"], "artifact": a["path"],
                "verdict": "descendant_or_same" if ok is not None else "not_a_descendant",
                "artifact_commit": a["last_commit"], "receipt_commit": v["last_commit"]})
    return out


# --------------------------------------------------------------------------- #
# the audit
# --------------------------------------------------------------------------- #
def audit_family(name: str, spec: dict | None = None, base: Path | None = None,
                 root: Path | None = None, adjudicated: dict | None = None,
                 mtime_tolerance_s: float = MTIME_TOLERANCE_S,
                 recount: bool = True, raise_on_block: bool = True) -> dict:
    """Audit one registered artifact family. Returns a machine-readable dict.

    ``base`` is the directory holding the family directory and the producer/validator sources
    (defaults to this module's directory). ``root`` is the repository root used to resolve pinned
    upstream inputs. Tests point both at temporary copies; nothing here writes.
    """
    spec = spec or FAMILIES[name]
    base = Path(base) if base is not None else HERE
    root = Path(root) if root is not None else ROOT
    adjudicated = adjudicated or {}
    fdir = base / spec["dir"]
    findings: list[dict] = []

    def add(kind: str, subject: str, **detail):
        findings.append({"family": name, "kind": kind, "subject": subject,
                         "link": KIND_LINK.get(kind, "artifact"), **detail})

    # -- input witnesses: recompute what a receipt claims ABOUT an upstream input ---- #
    witness_cache: dict[str, object] = {}
    witness_paths: dict[str, str] = {}

    def _witness(wname: str):
        """None means the input is not reachable from here; the caller reports it once."""
        if wname in witness_cache:
            return witness_cache[wname]
        w = (spec.get("witnesses") or {}).get(wname)
        if w is None:
            witness_cache[wname] = None
            return None
        anchor = base if w.get("anchor") == "base" else root
        p = anchor / w["path"]
        witness_paths[wname] = str(p)
        witness_cache[wname] = witness(wname, p, w["fn"]) if p.exists() else None
        return witness_cache[wname]

    # -- artifacts on disk and their true content hashes ---------------------- #
    actual_hash: dict[str, str] = {}
    artifact_mtime: dict[str, float] = {}
    for key, fname in spec["artifacts"].items():
        p = fdir / fname
        if not p.exists():
            add("artifact_missing", key, receipt="-", path=str(p))
            continue
        actual_hash[key] = sha256_file(p)
        artifact_mtime[key] = p.stat().st_mtime

    # -- producer / validator source hashes ---------------------------------- #
    src_hash: dict[str, str | None] = {}
    for role in ("producer", "validator"):
        rel = spec.get(role)
        if not rel:
            src_hash[role] = None
            continue
        p = base / rel
        src_hash[role] = sha256_file(p) if p.exists() else None

    # -- version columns carried by the artifact itself ----------------------- #
    artifact_versions: dict[str, dict[str, list]] = {}
    for key, cols in (spec.get("expected_versions") or {}).items():
        if key not in actual_hash:
            continue
        p = fdir / spec["artifacts"][key]
        for col, expected in cols.items():
            vals = _distinct_column_values(p, col)
            artifact_versions.setdefault(key, {})[col] = vals
            if len(vals) != 1:
                add("contract_version_divergence", f"{key}.{col}", receipt="-",
                    reason="the artifact does not carry one single version",
                    values_in_artifact=vals[:8])
            elif vals[0] != expected:
                add("contract_version_divergence", f"{key}.{col}", receipt="-",
                    reason="artifact version differs from the registered contract version",
                    in_artifact=vals[0], registered=expected)
    for b in spec.get("version_bindings") or []:
        key = b["artifact"]
        if key not in actual_hash:
            continue
        p = fdir / spec["artifacts"][key]
        vals = artifact_versions.get(key, {}).get(b["column"])
        if vals is None:
            vals = _distinct_column_values(p, b["column"])
            artifact_versions.setdefault(key, {})[b["column"]] = vals
        rp = fdir / b["receipt"]
        if not rp.exists():
            continue
        try:
            rj = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:                                                # noqa: BLE001
            continue
        rec = resolve(rj, b["path"])
        if rec is _MISSING:
            add("artifact_version_unbound", f"{key}.{b['column']}", receipt=b["receipt"],
                reason="the artifact carries this version but the receipt does not record it")
        elif len(vals) == 1 and str(rec) != vals[0]:
            add("contract_version_divergence", f"{key}.{b['column']}", receipt=b["receipt"],
                reason="version differs between artifact and receipt",
                in_artifact=vals[0], in_receipt=str(rec))

    # -- recount from the artifact bytes ------------------------------------- #
    counts: dict[str, int] = {}
    recount_error: str | None = None
    if recount and spec.get("recount") is not None and len(actual_hash) == len(spec["artifacts"]):
        try:
            counts = spec["recount"](fdir)
        except Exception as exc:                                         # noqa: BLE001
            recount_error = f"{type(exc).__name__}: {exc}"
            add("count_unrecomputable", "__recount__", receipt="-", error=recount_error)

    # -- per receipt ---------------------------------------------------------- #
    receipts_seen: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    for r in spec["receipts"]:
        rname = r["file"]
        rp = fdir / rname
        if not rp.exists():
            add("receipt_missing", rname, receipt=rname, path=str(rp))
            continue
        try:
            R = json.loads(rp.read_text(encoding="utf-8"))
        except Exception as exc:                                         # noqa: BLE001
            add("receipt_unreadable", rname, receipt=rname,
                error=f"{type(exc).__name__}: {exc}")
            continue
        receipts_seen[rname] = R
        rmtime = rp.stat().st_mtime
        created_at, created_path = _first_recorded_ts(R, r.get("created_at"))
        validated_at, validated_path = _first_recorded_ts(R, r.get("validated_at"))
        meta[rname] = {"file": rname, "role": r.get("role"), "R": R, "spec": r, "mtime": rmtime,
                       "certified": {}, "created_at": created_at, "validated_at": validated_at,
                       "instants": {}, "verdict": _MISSING}
        for label, p in (("created", created_path), ("validated", validated_path)):
            if p is not None:
                meta[rname]["instants"][label] = str(resolve(R, p))

        # identity / contract fields
        for label, path in (r.get("identity") or {}).items():
            got = resolve(R, path)
            want = (r.get("expect_identity") or {}).get(label)
            if got is _MISSING:
                add("contract_version_divergence", label, receipt=rname,
                    reason="the receipt does not state this contract field", expected=want)
            elif want is not None and got != want:
                add("contract_version_divergence", label, receipt=rname,
                    reason="the receipt states a different contract identity",
                    in_receipt=got, registered=want)

        # artifact content hashes
        for key in spec["artifacts"]:
            path = (r.get("hashes") or {}).get(key)
            if path is None:
                add("receipt_hash_absent", key, receipt=rname,
                    reason="this receipt declares no hash for a declared artifact")
                continue
            rec = resolve(R, path)
            if rec is _MISSING or not isinstance(rec, str):
                add("receipt_hash_absent", key, receipt=rname, json_path=list(path))
            else:
                meta[rname]["certified"][key] = rec
                if key in actual_hash and rec != actual_hash[key]:
                    add("artifact_hash_mismatch", key, receipt=rname,
                        in_receipt=rec, on_disk=actual_hash[key], cases=[1, 5],
                        reason="the receipt certifies bytes that are no longer on disk")

        # pinned upstream inputs
        for path, rel in (r.get("inputs") or {}).items():
            rec = resolve(R, path)
            if rec is _MISSING or not isinstance(rec, str):
                continue
            ip = root / rel
            if not ip.exists():
                add("input_hash_mismatch", rel, receipt=rname,
                    reason="a pinned upstream input is missing", in_receipt=rec, on_disk=None)
                continue
            got = sha256_file(ip)
            if got != rec:
                add("input_hash_mismatch", rel, receipt=rname,
                    in_receipt=rec, on_disk=got,
                    reason="a pinned upstream input changed after this receipt was written; "
                           "the artifact it certifies was built from different bytes")

        # producer / validator pinning. The validator is a DISTINCT link in the chain: an
        # unchanged producer says nothing about whether the code that issued the PASS moved.
        for role, key in (("producer", "producer_sha"), ("validator", "validator_sha")):
            absent_kind = "producer_sha_absent" if role == "producer" else "validator_sha_absent"
            drift_kind = ("producer_version_divergence" if role == "producer"
                          else "validator_version_divergence")
            path = r.get(key)
            if path is None:
                if role == "producer":
                    add("producer_sha_absent", role, receipt=rname,
                        reason="the receipt pins no producer, so producer drift is undetectable")
                elif (r.get("role") == "validation" and spec.get("validator")
                      and not _gap_declared(spec, rname, "validator_not_pinned")):
                    add("validator_sha_absent", role, receipt=rname,
                        reason="this validation receipt pins no validator source hash, so the "
                               "code that issued the verdict cannot be identified")
                continue
            rec = resolve(R, path)
            if rec is _MISSING or not isinstance(rec, str):
                add(absent_kind, role, receipt=rname, json_path=list(path))
            elif src_hash.get(role) is None:
                add(drift_kind, role, receipt=rname, cases=[3],
                    reason="the pinned source file is not on disk", in_receipt=rec, on_disk=None)
            elif rec != src_hash[role]:
                add(drift_kind, role, receipt=rname, cases=[3],
                    in_receipt=rec, on_disk=src_hash[role],
                    reason=f"the {role} source changed after this receipt was written")

        # the input manifest the VALIDATION run consumed, where the receipt pins it by hash
        for path, rel in (r.get("validated_inputs") or {}).items():
            rec = resolve(R, path)
            if rec is _MISSING or not isinstance(rec, str):
                add("validated_input_divergence", rel, receipt=rname, json_path=list(path),
                    in_receipt=None, cases=[3],
                    reason="the receipt declares this validated input but records no hash")
                continue
            ip = root / rel
            got = sha256_file(ip) if ip.exists() else None
            if got != rec:
                add("validated_input_divergence", rel, receipt=rname, cases=[3],
                    in_receipt=rec, on_disk=got,
                    reason="the validation run consumed bytes that are not the bytes on disk")
            for other, om in meta.items():
                if other == rname:
                    continue
                obuild = (om["spec"].get("inputs") or {})
                for opath, orel in obuild.items():
                    if orel != rel:
                        continue
                    orec = resolve(om["R"], opath)
                    if isinstance(orec, str) and orec != rec:
                        add("validated_input_divergence", rel, receipt=rname, cases=[3],
                            in_receipt=rec, in_build_receipt=orec, build_receipt=other,
                            reason="the validation run consumed a different version of this "
                                   "input than the build did")

        # input witnesses: numbers this receipt records ABOUT an upstream input, recomputed from
        # that input's current bytes. This is the only binding available where a receipt records
        # no input hash at all, and the only one possible for a cross-family count.
        for b in (spec.get("input_witnesses") or []):
            if b.get("receipt") != rname:
                continue
            rec = resolve(R, b["path"])
            if rec is _MISSING:
                continue
            w = _witness(b["witness"])
            if w is None:
                add("input_witness_unavailable", b["witness"], receipt=rname,
                    json_path=list(b["path"]),
                    path=witness_paths.get(b["witness"]),
                    reason="the upstream input this claim is about is not reachable from here")
                continue
            want = w if b.get("field") is None else w.get(b["field"], _MISSING)
            if want is _MISSING:
                add("input_witness_unavailable", f"{b['witness']}.{b.get('field')}",
                    receipt=rname, json_path=list(b["path"]),
                    reason="the witness produced no such field")
                continue
            if _canon(rec) != _canon(want):
                add("input_witness_divergence", f"{b['witness']}.{b.get('field') or '*'}",
                    receipt=rname, json_path=list(b["path"]), cases=[3],
                    in_receipt=_canon(rec) if not isinstance(rec, (dict, list)) else "<structure>",
                    recomputed=_canon(want) if not isinstance(want, (dict, list)) else "<structure>",
                    input_path=witness_paths.get(b["witness"]),
                    reason="a value this receipt records about an upstream input does not match "
                           "that input's current bytes; the run consumed different bytes")

        # recorded verdict
        vpath = r.get("verdict")
        if vpath is not None:
            v = resolve(R, vpath)
            meta[rname]["verdict"] = v
            if v is _MISSING or str(v).upper() != "PASS":
                add("validation_verdict_not_pass", "verdict", receipt=rname,
                    in_receipt=(None if v is _MISSING else v))

        # counts recorded vs counts recomputed
        bound = 0
        for c in r.get("counts") or []:
            ckey = c.get("count")
            if ckey is None:
                continue
            rec = resolve(R, c["path"])
            if rec is _MISSING:
                continue
            if ckey not in counts:
                if recount and recount_error is None and spec.get("recount") is not None:
                    add("count_unrecomputable", ckey, receipt=rname,
                        json_path=list(c["path"]),
                        error="no recount produced this key")
                continue
            bound += 1
            if int(rec) != int(counts[ckey]):
                add("count_divergence", ckey, receipt=rname,
                    json_path=list(c["path"]),
                    in_receipt=int(rec), recomputed=int(counts[ckey]),
                    delta=int(rec) - int(counts[ckey]))
        if bound == 0 and counts:
            add("receipt_records_no_counts", rname, receipt=rname,
                reason="nothing in this receipt could be cross-checked against the artifact")

        # rebuilt-without-revalidation, CORROBORATION ONLY: mtime is rewritten by a checkout or a
        # copy, so this is never the load-bearing detector. The hash and recorded-timestamp
        # checks below are.
        for key, amt in artifact_mtime.items():
            if rmtime + mtime_tolerance_s < amt:
                add("receipt_predates_artifact", key, receipt=rname, cases=[5],
                    artifact_mtime=datetime.fromtimestamp(amt, timezone.utc).isoformat(),
                    receipt_mtime=datetime.fromtimestamp(rmtime, timezone.utc).isoformat(),
                    seconds_stale=round(amt - rmtime, 3), evidence_class="mtime_corroboration",
                    reason="the artifact FILE is newer than this receipt FILE; mtime evidence "
                           "only, and mtime does not survive a checkout")

    # ======================================================================== #
    # the chain: validation execution and validation receipt
    #
    # everything above validates the artifact against its own manifest. That is exactly the check
    # that would have CLEARED the tree on 2026-08-04, because the target receipt had not drifted.
    # What follows is the part that would have caught it.
    # ======================================================================== #
    prod_meta = [m for m in meta.values() if m["role"] == "producer"]
    val_meta = [m for m in meta.values() if m["role"] == "validation"]

    # a family with a validator must register something that evidences its execution
    if spec.get("validator") and not [r for r in spec["receipts"] if r.get("role") == "validation"]:
        add("validation_link_absent", "validation", receipt="-",
            validator=spec.get("validator"),
            reason="this family declares a validator but registers no validation receipt, so "
                   "nothing on disk evidences that validation ever ran")

    # the two receipts must agree about which bytes exist. If they disagree, at most one of them
    # describes the run that produced what is on disk -- and the PASS may be the other one.
    for key in spec["artifacts"]:
        pins = {n: m["certified"][key] for n, m in meta.items() if key in m["certified"]}
        if len(set(pins.values())) > 1:
            add("receipt_hash_disagreement", key, receipt="+".join(sorted(pins)), cases=[1],
                pins=pins, on_disk=actual_hash.get(key),
                reason="two receipts in this family certify different bytes for one artifact, so "
                       "at most one of them describes the artifact on disk")

    # is the TARGET receipt itself current? This is what separates the defect that occurred
    # (case 1: manifest current, verdict stale) from a wholesale rebuild.
    target_current = None
    if prod_meta and actual_hash:
        target_current = all(m["certified"].get(k) == actual_hash[k]
                             for m in prod_meta for k in actual_hash)

    created = [(m["created_at"], m["file"]) for m in prod_meta if m["created_at"] is not None]
    created_at, created_by = (max(created, key=lambda t: t[0]) if created else (None, None))

    for m in val_meta:
        rname = m["file"]
        is_pass = m["verdict"] is not _MISSING and str(m["verdict"]).upper() == "PASS"
        evidence: list[dict] = []

        # (a) HASH EVIDENCE -- survives a checkout, unlike mtime. Does the PASS certify the bytes
        #     that are on disk right now?
        for key in spec["artifacts"]:
            disk = actual_hash.get(key)
            if disk is None:
                continue
            cert = m["certified"].get(key)
            if cert is None:
                evidence.append({"evidence": "verdict_certifies_no_bytes", "artifact": key})
            elif cert != disk:
                evidence.append({"evidence": "certified_hashes_are_not_the_artifact",
                                 "artifact": key, "certifies": cert, "on_disk": disk})

        # (b) RECORDED-TIMESTAMP EVIDENCE -- also survives a checkout, because the receipts write
        #     these instants into their own JSON.
        timeline_stale = False
        if m["validated_at"] is not None and created_at is not None:
            if not m["validated_at"] > created_at:
                timeline_stale = True
                add("validation_precedes_artifact", "timeline", receipt=rname, cases=[2, 5],
                    validated_utc=m["instants"].get("validated"),
                    artifact_generated_utc=created_by and meta[created_by]["instants"].get("created"),
                    generated_by=created_by,
                    seconds_early=round((created_at - m["validated_at"]).total_seconds(), 3),
                    mtime_corroborates=bool(
                        artifact_mtime and m["mtime"] + mtime_tolerance_s < max(artifact_mtime.values())),
                    reason="the instant this validation RECORDS for itself is not strictly after "
                           "the instant the build RECORDS for the artifact; the verdict cannot "
                           "be about these bytes")
                evidence.append({"evidence": "verdict_predates_the_artifact",
                                 "validated_utc": m["instants"].get("validated"),
                                 "artifact_generated_utc":
                                     created_by and meta[created_by]["instants"].get("created")})
        elif m["validated_at"] is not None and created_at is None:
            add("validation_timeline_unbound", "timeline", receipt=rname,
                reason="no producer receipt records a creation instant, so the validation "
                       "timestamp cannot be ordered against the artifact")

        # THE FINDING THIS MODULE EXISTS FOR. A PASS is a claim about specific bytes at a
        # specific moment. If either is wrong the PASS is stale, and a stale PASS is worse than
        # no receipt, because a reader stops looking.
        if is_pass and evidence:
            cases = set()
            hash_stale = any(e["evidence"] != "verdict_predates_the_artifact" for e in evidence)
            if hash_stale and target_current:
                cases.add(1)
            if timeline_stale:
                cases.add(2)
            if hash_stale and timeline_stale:
                cases.add(5)
            if hash_stale and target_current is False:
                cases.add(5)
            for e in evidence:
                subject = e.get("artifact", "timeline")
                add("stale_validation_verdict", subject, receipt=rname,
                    cases=sorted(cases) or [1], target_receipt_current=target_current,
                    verdict=m["verdict"], **{k: v for k, v in e.items() if k != "artifact"},
                    reason="this receipt records PASS for bytes that are not the bytes on disk "
                           "now; the verdict certifies nothing about this artifact")

    # (c) FRESHNESS. Read the kind name literally: it says a fresh execution is NOT PROVEN. It
    #     does not say validation did not happen -- nothing on disk could support that claim.
    stamped: dict[str, list[str]] = {}
    for n, m in meta.items():
        for label, s in m["instants"].items():
            if s and s != "None":
                stamped.setdefault(s, []).append(f"{n}:{label}")
    for s, who in stamped.items():
        if len(who) > 1 and any(w.endswith(":validated") for w in who):
            add("fresh_execution_not_proven", "recorded_instant", receipt="+".join(
                sorted({w.split(':')[0] for w in who})), cases=[4], instant=s, recorded_by=who,
                reason="two recorded instants in this family are identical to the microsecond. "
                       "Independent executions do not finish in the same instant, so this "
                       "receipt may have been copied forward. This is NOT a claim that "
                       "validation did not run -- see UNIVERSAL_GAPS/fresh_execution_unprovable")
    token_path = spec.get("run_token")
    if token_path:
        seen: dict[str, list[str]] = {}
        for n, m in meta.items():
            t = resolve(m["R"], token_path)
            if isinstance(t, str) and t:
                seen.setdefault(t, []).append(n)
        for t, who in seen.items():
            if len(who) > 1:
                add("fresh_execution_not_proven", "run_token", receipt="+".join(sorted(who)),
                    cases=[4], token=t, recorded_by=who,
                    reason="two receipts carry the same per-execution token, so at most one of "
                           "them is the record of a fresh execution")

    # -- declared gaps: structural limits of what these receipts make checkable ---- #
    gaps: list[dict] = []
    for g in _gaps_for(spec):
        targets = ([r["file"] for r in spec["receipts"]] if g.get("receipt") == "*"
                   else [g.get("receipt")])
        probes = g.get("probe")
        probes = [probes] if isinstance(probes, tuple) else list(probes or [])
        closed_in = []
        for t in targets:
            R = receipts_seen.get(t)
            if R is None:
                continue
            if any(resolve(R, p) is not _MISSING for p in probes):
                closed_in.append(t)
        entry = {"family": name, **{k: v for k, v in g.items() if k != "probe"},
                 "still_open": not closed_in}
        gaps.append(entry)
        if closed_in:
            add("gap_declaration_stale", g.get("gap", "?"), receipt="+".join(closed_in),
                reason="this gap is declared permanent but the receipt now records the evidence; "
                       "close the declaration and bind the field")

    # -- adjudication and verdict -------------------------------------------- #
    blocking = []
    for f in findings:
        if f["kind"] not in BLOCKING:
            continue
        adj = _adjudication_for(f, adjudicated)
        if adj:
            f["adjudicated"] = adj
        else:
            blocking.append(f)

    chain = {link: {"findings": 0, "blocking": 0} for link in CHAIN}
    for f in findings:
        c = chain.setdefault(f.get("link", "artifact"), {"findings": 0, "blocking": 0})
        c["findings"] += 1
        c["blocking"] += 1 if f in blocking else 0

    out = {
        "family": name,
        "artifact_id": spec.get("artifact_id"),
        "dir": str(fdir),
        "artifacts": {k: {"file": spec["artifacts"][k], "sha256": actual_hash.get(k)}
                      for k in spec["artifacts"]},
        "producer_sha256": src_hash.get("producer"),
        "validator_sha256": src_hash.get("validator"),
        "artifact_versions": artifact_versions,
        "recomputed_counts": counts,
        "recount_error": recount_error,
        "receipts_checked": [r["file"] for r in spec["receipts"]],
        "chain": chain,
        "target_receipt_current": target_current,
        "artifact_generated_utc": created_by and meta[created_by]["instants"].get("created"),
        "validated_utc": {m["file"]: m["instants"].get("validated") for m in val_meta},
        "input_witnesses_checked": sorted(w for w, v in witness_cache.items() if v is not None),
        "gaps": gaps,
        "findings": findings,
        "blocking": blocking,
        "passed": len(blocking) == 0,
        "note": "a receipt is a claim about specific bytes AND a specific moment; a PASS whose "
                "hashes or whose recorded instant do not match the artifact certifies nothing",
    }
    if blocking and raise_on_block:
        raise ReceiptIntegrityFailure(json.dumps(blocking[:6], default=str))
    return out


def sweep(families: list[str] | None = None, base: Path | None = None, root: Path | None = None,
          adjudicated: dict | None = None, mtime_tolerance_s: float = MTIME_TOLERANCE_S,
          recount: bool = True, raise_on_block: bool = True, specs: dict | None = None,
          lineage: bool = False) -> dict:
    """Audit every registered family. Never stops at the first failure."""
    specs = specs or FAMILIES
    names = families or list(specs)
    results, blocking = {}, []
    for n in names:
        r = audit_family(n, spec=specs[n], base=base, root=root, adjudicated=adjudicated,
                         mtime_tolerance_s=mtime_tolerance_s, recount=recount,
                         raise_on_block=False)
        results[n] = r
        blocking.extend(r["blocking"])

    # cross-family freshness: two independent validation runs anywhere in the program cannot have
    # finished in the same microsecond. Reported, again, as "not proven fresh", never as "did not
    # run" -- see UNIVERSAL_GAPS/fresh_execution_unprovable.
    stamped: dict[str, list[str]] = {}
    for n in names:
        for rname, s in (results[n].get("validated_utc") or {}).items():
            if s and s != "None":
                stamped.setdefault(s, []).append(f"{n}/{rname}")
    for s, who in stamped.items():
        if len(who) > 1:
            f = {"family": "+".join(sorted({w.split('/')[0] for w in who})),
                 "kind": "fresh_execution_not_proven", "subject": "recorded_instant",
                 "link": "validation_execution", "receipt": "+".join(sorted(who)),
                 "cases": [4], "instant": s, "recorded_by": who,
                 "reason": "two validation receipts in different families record the identical "
                           "instant; at most one of them is the record of a fresh execution"}
            for n in names:
                if n in f["family"]:
                    results[n]["findings"].append(f)
                    results[n]["blocking"].append(f)
                    results[n]["passed"] = False
            blocking.append(f)

    gaps = [g for n in names for g in (results[n].get("gaps") or [])]
    out = {
        "schema": "receipt_integrity_sweep/2",
        "swept_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "chain": list(CHAIN),
        "cases": CASES,
        "families": names,
        "per_family": {n: {"passed": results[n]["passed"],
                           "n_findings": len(results[n]["findings"]),
                           "n_blocking": len(results[n]["blocking"]),
                           "blocking_kinds": sorted({f["kind"] for f in results[n]["blocking"]}),
                           "counts_cross_checked": len(results[n]["recomputed_counts"]),
                           "input_witnesses_checked":
                               len(results[n].get("input_witnesses_checked") or []),
                           "target_receipt_current": results[n].get("target_receipt_current"),
                           "chain": results[n].get("chain")}
                       for n in names},
        "results": results,
        "gaps": gaps,
        "open_gaps": [g for g in gaps if g.get("still_open")],
        "blocking": blocking,
        "blocking_kinds": sorted({f["kind"] for f in blocking}),
        "cases_seen": sorted({c for f in blocking for c in (f.get("cases") or [])}),
        "passed": len(blocking) == 0,
    }
    if lineage:
        out["git_lineage"] = {n: git_lineage(n, spec=specs[n], base=base, root=root)
                              for n in names}
    if blocking and raise_on_block:
        raise ReceiptIntegrityFailure(json.dumps(blocking[:6], default=str))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="receipt-integrity sweep")
    ap.add_argument("--family", action="append", choices=sorted(FAMILIES),
                    help="restrict the sweep (repeatable)")
    ap.add_argument("--json", type=Path, help="write the full machine-readable sweep here")
    ap.add_argument("--no-recount", action="store_true",
                    help="skip artifact recomputation (hash and version checks only)")
    ap.add_argument("--git-lineage", action="store_true",
                    help="also reconstruct commit ancestry (corroboration; never blocking)")
    a = ap.parse_args(argv)

    s = sweep(families=a.family, recount=not a.no_recount, raise_on_block=False,
              lineage=a.git_lineage)
    print(f"  chain: {' -> '.join(CHAIN)}")
    for n in s["families"]:
        r = s["per_family"][n]
        print(f"  {'PASS' if r['passed'] else 'FAIL'}  {n:<24} "
              f"findings {r['n_findings']:>2}  blocking {r['n_blocking']:>2}  "
              f"counts cross-checked {r['counts_cross_checked']:>2}  "
              f"input witnesses {r['input_witnesses_checked']:>2}  "
              f"target receipt current {str(r['target_receipt_current']):>5}")
    for f in s["blocking"]:
        cases = "".join(f" case{c}" for c in (f.get("cases") or []))
        print(f"    BLOCK {f['family']}/{f.get('receipt', '-')}: {f['kind']} [{f['subject']}]"
              f"{cases} {f.get('reason', '')}")
    for g in s["open_gaps"]:
        print(f"    GAP   {g['family']}/{g.get('receipt', '*')}: {g['gap']} ({g['link']}) "
              f"-- {g['why'][:110]}...")
    if a.git_lineage:
        for n, L in s["git_lineage"].items():
            for v in L.get("verdicts", []):
                print(f"    LINEAGE {n}/{v['receipt']}: {v['verdict']}")
    if a.json:
        a.json.write_text(json.dumps(s, indent=2, default=str), encoding="utf-8")
        print(f"  wrote {a.json}")
    print(f"\n{'PASS' if s['passed'] else 'FAIL'} -- {len(s['blocking'])} blocking finding(s) "
          f"across {len(s['families'])} famil{'y' if len(s['families']) == 1 else 'ies'}")
    return 0 if s["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
