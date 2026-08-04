#!/usr/bin/env python3
"""construction_receipt.py — PERMANENT producer-emitted FEATURE CONSTRUCTION receipt.

Born from the CALLER-MANUFACTURED PROVENANCE defect. ``gate_invocation.audit_fold`` accepts a
``provenance=`` mapping, and that mapping is built **by the caller, at the invocation site, after
the frame already exists**. Everything in it is a string the caller chose:
``producer_source_path`` names any readable file, ``input_manifest`` names any readable files,
``row_universe_digest`` is recomputed from the very frame being presented, and
``feature_construction_receipt`` was accepted if it merely *existed on disk*. A model runner that
wrote::

    provenance={"producer_source_path": __file__,
                "row_universe_digest": gi.index_digest(df.index, sort=True,
                                                       label="raw_index_membership")}

reached ``IDENTITY_VERIFIED`` — a full Stage 1 pass — having demonstrated nothing except that it
could hash its own source file and re-digest the frame it was already holding. The repository
could not independently show that the frame called "raw" came from the claimed producer, because
**no producer in this repository ever emitted a construction receipt at all.**

What the producers DO emit is an ARTIFACT receipt: ``PROJECTED_EXPOSURE_RECEIPT.json`` records
which bytes were written, their hashes, their row counts and their distributions. That is a claim
about an OUTPUT. It says nothing about how a downstream FEATURE FRAME was built from that output:
which rows were selected, which columns were declared, in which order, under which cutoff, for
which chronological fold, and whether the frame handed to a fitter is the frame the producer
actually constructed. Those are different questions and they need a different receipt.

WHAT A CONSTRUCTION RECEIPT BINDS
---------------------------------
Every receipt this module emits carries, and every verification re-derives from on-disk reality:

    experiment / arm / fold / scope identity      producer module path
    producer source digest                        producing commit (and whether it was dirty)
    invocation and run identity                   target cutoff / decision-time contract
    chronological fold identity                   exact source artifact paths and hashes
    cutoff-validity declaration per source         candidate / team-game universe digest
    row-identity digest (order AND membership)    feature names and feature ORDER
    raw feature-frame digest                      per-column raw missingness-mask digests
    declared transformation (or none)             output artifact or frame digest
    generation result and failure state

TWO BLOCKS, AND THEY ARE NOT THE SAME CLAIM
-------------------------------------------
A receipt is split into two separately labelled blocks and a reader must never conflate them:

``frozen_source_provenance``
    provenance OF THE FROZEN INPUT ARTIFACTS, which this receipt does **not** establish. It
    records their paths, their current hashes, and the status of the artifact and validation
    receipts that ALREADY existed for them, including whether those receipts still certify the
    bytes on disk. Nothing here is newly proven construction provenance for those artifacts; their
    original construction remains attested only by their own legacy receipts.

``produced_frame_provenance``
    provenance OF THE FEATURE FRAME THIS PRODUCER JUST EMITTED, which this receipt does establish:
    the producer source that ran, the commit it ran at, the universe it drew, the fold it built
    for, the columns it declared, and the exact bytes of the frame it returned.

EMISSION IS STRUCTURAL, NOT CONVENTIONAL
----------------------------------------
The receipt is emitted BY THE PRODUCER, DURING construction, and is never assembled afterward by a
model runner:

1. ``emit_construction_receipt`` resolves the producer's source path **by walking the stack** to
   the first frame outside this module. It is not a caller-supplied string. (An explicit override
   exists for generated or copied producers; it is recorded as ``resolution: "explicit"`` and the
   file it names is hashed and re-hashed at verification exactly the same way.)
2. It requires the FRAME OBJECT. Digests are taken from the frame in memory at construction time;
   there is no code path that accepts a digest the caller computed.
3. It requires every source artifact to be readable AT EMISSION and hashes each one itself.
4. It refuses to emit an incoherent receipt — a positional row index, an undeclared feature, a
   feature source that does not assert cutoff validity — by raising, so a producer that cannot
   describe its own construction produces no frame either.
5. It writes to disk and reads the file back before returning. A receipt that cannot be written is
   a construction failure, not a warning.
6. Verification takes a PATH. It re-hashes the producer file, re-hashes every source artifact,
   re-derives every frame digest from the frame presented, and recomputes the receipt's own
   self-binding digest. ``gate_invocation`` grants a verified assurance level only through this
   path; an inline mapping cannot reach one.

**Known limit, stated rather than smoothed over:** anyone who can write files can write a file.
This module does not and cannot prove that a human did not fabricate a receipt by hand. What it
makes structurally impossible is a receipt that is *cheap*: a forgery must reproduce the
producer's exact source bytes, every source artifact's exact bytes, the exact row universe, the
exact column order and the exact frame values, and must survive re-derivation against the files
that exist at verification time. The gate's raw-frame audit remains the primary leakage control;
this receipt is the lineage control.

House style: a ``*Failure`` exception, machine-readable dicts, an explicit ``BLOCKING`` set.

Pure stdlib + numpy/pandas. Python 3.13. Nothing here is fitted and nothing here is scored.

Run::  python experiments/player_program/construction_receipt.py
"""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np, pandas as pd                                                # noqa: E401

_THIS_FILE = Path(__file__).resolve()

CONSTRUCTION_RECEIPT_SCHEMA = "construction_receipt/1"
VERIFICATION_SCHEMA = "construction_receipt.verification/1"

#: the roles a declared source may play. The distinction is load-bearing: an OUTCOME source is
#: not cutoff-valid by definition and must never contribute a feature column, while a FEATURE
#: source that is not cutoff-valid is a leak.
SOURCE_ROLES: tuple[str, ...] = ("feature_source", "outcome_source", "universe_source",
                                 "reference_receipt")

GENERATION_RESULTS: tuple[str, ...] = ("ok", "failed")

#: the claim boundary carried by every receipt. A caller may ADD to it; it cannot be removed.
CLAIM_BOUNDARY: dict[str, str] = {
    "establishes": (
        "producer-backed provenance for the feature frame THIS producer emitted: the producer "
        "source that ran, the commit it ran at, the frozen source bytes it read, the universe it "
        "drew, the fold it built for, the columns it declared and the exact frame it returned"),
    "does_not_establish": (
        "how the frozen SOURCE artifacts were originally constructed. Their construction is "
        "attested only by the artifact and validation receipts that already existed for them. "
        "This receipt does not add construction provenance to any upstream canonical artifact, "
        "and a reader must not read it as doing so"),
    "frozen_source_provenance_status": "legacy_receipts_only",
}

#: finding kinds that invalidate a construction receipt. A receipt carrying any of these is not
#: evidence: it is a document about a construction that cannot be shown to have happened.
BLOCKING: set[str] = {
    # -- the receipt as a document ----------------------------------------------------------
    "construction_receipt_absent", "construction_receipt_unreadable",
    "construction_receipt_not_a_mapping", "construction_receipt_schema_unrecognised",
    "construction_receipt_self_binding_broken", "construction_receipt_incomplete",
    # -- the producer that emitted it ---------------------------------------------------------
    "producer_source_unreadable", "producer_source_digest_mismatch",
    "producing_commit_unrecorded",
    # -- the frozen sources it read -------------------------------------------------------------
    "source_artifact_unreadable", "source_artifact_digest_mismatch",
    "source_cutoff_validity_undeclared", "source_not_cutoff_valid_for_features",
    "source_manifest_mismatch",
    # -- the frame it produced -------------------------------------------------------------------
    "universe_contract_mismatch", "row_universe_mismatch", "row_order_mismatch",
    "feature_set_mismatch", "raw_frame_digest_mismatch", "missingness_digest_mismatch",
    "gate_argument_digest_mismatch", "output_digest_mismatch",
    # -- what it was built for ---------------------------------------------------------------------
    "fold_identity_mismatch", "cutoff_contract_mismatch",
    # -- the construction itself ---------------------------------------------------------------------
    "construction_failed", "receipt_unwritable",
}

#: recorded, never blocking. Listed so that "not in BLOCKING" is a deliberate statement.
INFORMATIONAL: set[str] = {
    "construction_receipt_verified", "source_is_outcome_not_feature",
    "frozen_source_receipt_unavailable", "frozen_source_receipt_stale",
    "producing_commit_dirty", "no_gate_arguments_declared", "no_output_declared",
    "producer_resolution_explicit",
}


class ConstructionReceiptFailure(RuntimeError):
    """Raised when a construction cannot be described honestly, or its receipt cannot be written.

    A producer that raises this has produced no frame. That is the point: a feature frame whose
    construction cannot be recorded is a feature frame with no construction provenance, and the
    whole defect this module closes is treating that state as ordinary.
    """


# --------------------------------------------------------------------------------------------
# digests
#
# These are byte-identical in behaviour to ``gate_invocation``'s primitives ON PURPOSE. The gate
# compares the digests THIS module recorded at construction time against the digests IT computes
# from the frame presented at audit time, so the two algebras must agree exactly. They are
# duplicated rather than imported because a PRODUCER must not depend on the gate that audits it.
# ``test_construction_receipt.py`` asserts the agreement executably, so the duplication cannot
# drift silently.
# --------------------------------------------------------------------------------------------

def scalar_repr(v: Any) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "True" if bool(v) else "False"
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    if isinstance(v, (int, np.integer)):
        return repr(int(v))
    if v is None:
        return "None"
    if isinstance(v, tuple):
        return "\x1f".join(scalar_repr(x) for x in v)
    return str(v)


def digest_of(vals: Sequence[str], label: str) -> str:
    h = hashlib.sha256("\x00".join(vals).encode("utf-8")).hexdigest()
    return f"{label}:n={len(vals)}:sha256={h[:32]}"


def _values_list(v: Any) -> list:
    if isinstance(v, (pd.Series, pd.Index)):
        return v.tolist()
    if isinstance(v, np.ndarray):
        return v.tolist()
    return list(v)


def values_digest(v: Any, *, label: str = "values") -> str:
    """Digest of VALUES in row order, independent of any index."""
    if isinstance(v, pd.DataFrame):
        head = "\x1e".join(str(c) for c in v.columns)
        rows = ["\x1f".join(scalar_repr(x) for x in t)
                for t in v.itertuples(index=False, name=None)]
        return digest_of([head] + rows, label)
    return digest_of([scalar_repr(x) for x in _values_list(v)], label)


def index_digest(idx: Any, *, sort: bool = False, label: str | None = None) -> str:
    """Digest of ROW IDENTITY. ``sort=True`` digests the membership, ``sort=False`` the order."""
    labels = [scalar_repr(x) for x in _values_list(idx)]
    if sort:
        labels = sorted(labels)
    return digest_of(labels, label or ("index_membership" if sort else "index"))


def matrix_digest(m: Any, names: Sequence[str], *, label: str = "audited_matrix") -> str | None:
    """Digest of a feature MATRIX, comparable across DataFrame and ndarray presentations."""
    names = [str(c) for c in names]
    try:
        if isinstance(m, pd.DataFrame):
            cols = [c for c in names if c in m.columns]
            sub = m.loc[:, cols] if len(cols) == len(names) else m
            sub = sub.copy()
            sub.columns = [str(c) for c in sub.columns]
        else:
            a = np.asarray(m)
            if a.ndim == 1:
                a = a.reshape(-1, 1)
            if a.ndim != 2:
                return None
            cols = (list(names) if a.shape[1] == len(names)
                    else [f"__col{i}__" for i in range(a.shape[1])])
            sub = pd.DataFrame(a, columns=cols)
        return values_digest(sub, label=label)
    except Exception:                                            # pragma: no cover - defensive
        return None


def missingness_profile(frame: Any, names: Sequence[str]) -> dict:
    """Per-column null-mask digests plus an aggregate over them.

    A frame with no missingness still gets a profile: the all-zero mask digest of a column that
    HAS no nulls is the evidence that it had none, and "there were no nulls" is a claim exactly
    like any other.
    """
    out: dict[str, Any] = {"per_column": {}, "n_missing_cells": 0, "columns_with_missing": []}
    if not isinstance(frame, pd.DataFrame):
        return out
    total = 0
    for c in [str(x) for x in names]:
        if c not in frame.columns:
            continue
        miss = frame[c].isna().to_numpy()
        n_miss = int(miss.sum())
        total += n_miss
        out["per_column"][c] = {
            "missing_mask_digest": digest_of([("1" if b else "0") for b in miss.tolist()],
                                             f"missing_mask[{c}]"),
            "n_missing": n_miss, "n_rows": int(miss.size),
            "missing_rate": round(n_miss / miss.size, 8) if miss.size else None,
        }
        if n_miss:
            out["columns_with_missing"].append(c)
    out["n_missing_cells"] = total
    per = out["per_column"]
    out["aggregate_digest"] = digest_of(
        [f"{c}={per[c]['missing_mask_digest']}" for c in sorted(per)], "missingness")
    return out


def _sha256_file(p: str | Path | None) -> str | None:
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest() if p else None
    except Exception:
        return None


def _size(p: str | Path | None) -> int | None:
    try:
        return int(Path(p).stat().st_size)
    except Exception:
        return None


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _dig(obj: Any, key_path: Sequence[Any] | None) -> Any:
    """Read a nested value out of a parsed receipt by key path. Returns ``None`` on any miss."""
    if not key_path:
        return None
    cur = obj
    for k in key_path:
        try:
            cur = cur[k]
        except Exception:
            return None
    return cur


def _finding(kind: str, **kw: Any) -> dict:
    return {"kind": kind, **kw}


# --------------------------------------------------------------------------------------------
# producer and commit identity -- resolved by this module, never supplied by the caller
# --------------------------------------------------------------------------------------------

def producer_identity(explicit_path: str | Path | None = None) -> dict:
    """Identify the producer that is calling ``emit``: the first stack frame outside this module.

    The stack walk is the structural part. A receipt whose producer identity were a caller-passed
    string would be exactly the ``provenance=`` mapping this module replaces.
    """
    if explicit_path is not None:
        p = str(Path(explicit_path).resolve())
        return {"source_path": p, "source_sha256": _sha256_file(p),
                "source_bytes": _size(p), "function": None, "resolution": "explicit"}
    try:
        for fr in inspect.stack()[1:]:
            fn = fr.filename
            if not fn:
                continue
            try:
                if Path(fn).resolve() == _THIS_FILE:
                    continue
            except Exception:                                    # pragma: no cover - defensive
                continue
            p = str(Path(fn).resolve())
            return {"source_path": p, "source_sha256": _sha256_file(p),
                    "source_bytes": _size(p), "function": fr.function, "resolution": "stack"}
    except Exception:                                            # pragma: no cover - defensive
        pass
    return {"source_path": None, "source_sha256": None, "source_bytes": None,
            "function": None, "resolution": "unresolved"}


def producing_commit(repo_root: str | Path | None = None) -> dict:
    """The commit the producer ran at, read from git. READ-ONLY git; nothing is written."""
    root = Path(repo_root) if repo_root else _THIS_FILE.parent
    rec: dict[str, Any] = {"resolved": False, "sha": None, "branch": None,
                           "worktree_dirty": None, "reason": None}

    def _git(*args: str) -> str | None:
        try:
            out = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                 text=True, timeout=30)
        except Exception as e:                                   # pragma: no cover - defensive
            rec["reason"] = repr(e)
            return None
        if out.returncode != 0:
            rec["reason"] = (out.stderr or "").strip()[:200]
            return None
        return out.stdout.strip()

    sha = _git("rev-parse", "HEAD")
    if sha:
        rec.update({"resolved": True, "sha": sha,
                    "branch": _git("rev-parse", "--abbrev-ref", "HEAD")})
        dirty = _git("status", "--porcelain", "--untracked-files=no")
        rec["worktree_dirty"] = (dirty is None) or bool(dirty.strip())
    return rec


# --------------------------------------------------------------------------------------------
# declarations the producer makes about its own construction
# --------------------------------------------------------------------------------------------

def source_declaration(path: str | Path, *, role: str, cutoff_valid: bool,
                       cutoff_rationale: str, artifact_id: str | None = None,
                       coverage: Mapping[str, Any] | None = None,
                       artifact_receipt: Mapping[str, Any] | None = None,
                       validation_receipt: Mapping[str, Any] | None = None,
                       repo_root: str | Path | None = None) -> dict:
    """Declare ONE frozen source artifact, hash it, and bind the receipts that already cover it.

    ``cutoff_valid`` is an assertion the producer makes and this module cannot verify — cutoff
    validity is a property of how the bytes were built, and that is upstream. What it CAN do is
    refuse to proceed without the assertion and a stated rationale, and bind both into the receipt
    forever. A ``feature_source`` that does not assert ``cutoff_valid=True`` raises here rather
    than reaching a frame.

    ``artifact_receipt`` / ``validation_receipt`` are optional and take the shape::

        {"path": "...json",
         "records_artifact_sha256_at": ["outputs", "team_possession_prior_v1.parquet", "sha256"],
         "verdict_at": ["verdict"]}                       # validation receipts only

    The named receipt is read, hashed, and the hash it records for THIS artifact is compared with
    the artifact's bytes on disk now. A receipt that certifies different bytes than the ones being
    read is recorded as stale — the ``receipt_integrity`` lesson, applied at construction time.
    """
    p = Path(path).resolve()
    role = str(role)
    if role not in SOURCE_ROLES:
        raise ConstructionReceiptFailure(
            f"unknown source role {role!r}; known roles are {SOURCE_ROLES}")
    if not (isinstance(cutoff_rationale, str) and cutoff_rationale.strip()):
        raise ConstructionReceiptFailure(
            f"source {p.name}: cutoff_rationale is mandatory and is carried in the receipt forever")
    if cutoff_valid is not True and cutoff_valid is not False:
        raise ConstructionReceiptFailure(
            f"source {p.name}: cutoff_valid must be declared True or False, not {cutoff_valid!r}")
    sha = _sha256_file(p)
    if sha is None:
        raise ConstructionReceiptFailure(
            f"source {p} is unreadable at construction time; a producer that cannot read its "
            f"inputs has produced nothing")
    if role == "feature_source" and cutoff_valid is not True:
        raise ConstructionReceiptFailure(
            f"source {p.name} is declared a feature_source and does NOT assert cutoff validity. "
            f"A feature built from information unavailable at the decision time is a leak, and it "
            f"is refused here rather than audited later")

    rel = None
    if repo_root is not None:
        try:
            rel = str(p.relative_to(Path(repo_root).resolve())).replace("\\", "/")
        except Exception:
            rel = None

    def _bound_receipt(spec: Mapping[str, Any] | None, want_verdict: bool) -> dict | None:
        if spec is None:
            return None
        rp = Path(spec["path"]).resolve()
        rsha = _sha256_file(rp)
        rec: dict[str, Any] = {"path": str(rp), "sha256": rsha,
                               "records_artifact_sha256_at":
                                   list(spec.get("records_artifact_sha256_at") or []),
                               "recorded_artifact_sha256": None,
                               "matches_current_artifact_bytes": None,
                               "verdict": None, "readable": rsha is not None}
        if rsha is None:
            return rec
        try:
            body = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            rec["readable"] = False
            return rec
        rec["schema"] = body.get("schema")
        recorded = _dig(body, spec.get("records_artifact_sha256_at"))
        if isinstance(recorded, str):
            rec["recorded_artifact_sha256"] = recorded
            rec["matches_current_artifact_bytes"] = bool(recorded == sha)
        if want_verdict:
            rec["verdict_at"] = list(spec.get("verdict_at") or ["verdict"])
            rec["verdict"] = _dig(body, rec["verdict_at"])
        return rec

    return {
        "path": str(p),
        "path_relative_to_root": rel,
        "role": role,
        "artifact_id": artifact_id,
        "sha256": sha,
        "bytes": _size(p),
        "cutoff_valid": bool(cutoff_valid),
        "cutoff_rationale": cutoff_rationale.strip(),
        "coverage": dict(coverage or {}),
        "artifact_receipt": _bound_receipt(artifact_receipt, want_verdict=False),
        "validation_receipt": _bound_receipt(validation_receipt, want_verdict=True),
    }


def universe_contract(frame: pd.DataFrame, *, contract_id: str,
                      row_identity_columns: Sequence[str], description: str,
                      restrictions: Sequence[Mapping[str, Any]] | None = None) -> dict:
    """The SHARED, digested row universe every downstream construction must draw from.

    Incumbent inputs, matched K0 inputs and challenger feature frames are only comparable if they
    are about the same rows. Digesting the universe ONCE and binding that digest into every
    construction receipt is what makes "same universe" checkable instead of assumed; a challenger
    documented against a universe the incumbent never saw is the parity defect this program has
    already paid for once, and it is refused here by construction.
    """
    if not isinstance(frame, pd.DataFrame):
        raise ConstructionReceiptFailure("the universe must be a pandas DataFrame")
    cols = [str(c) for c in row_identity_columns]
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise ConstructionReceiptFailure(
            f"the universe frame does not carry its own row-identity columns: {missing}")
    if not (isinstance(description, str) and description.strip()):
        raise ConstructionReceiptFailure("a universe contract carries a stated description")
    keys = frame[cols].astype(str).agg(":".join, axis=1)
    if keys.duplicated().any():
        raise ConstructionReceiptFailure(
            "the declared row-identity columns do not identify rows uniquely; a universe whose "
            "rows cannot be named cannot be shared between incumbent, K0 and challenger")
    return {
        "universe_contract_id": str(contract_id),
        "description": description.strip(),
        "row_identity_columns": cols,
        "n_rows": int(len(frame)),
        "row_universe_digest": index_digest(keys, sort=True, label="raw_index_membership"),
        "row_order_digest": index_digest(keys, label="raw_index"),
        "universe_key_columns_digest": values_digest(frame[cols], label="universe_keys"),
        "restrictions": [dict(r) for r in (restrictions or [])],
    }


def cutoff_contract(*, decision_time_rule: str, per_row_decision_time_column: str | None = None,
                    fold_cutoff: Any = None, target_cutoff: Any = None,
                    notes: str | None = None) -> dict:
    """The decision-time contract every column in the frame is claimed to respect."""
    if not (isinstance(decision_time_rule, str) and decision_time_rule.strip()):
        raise ConstructionReceiptFailure(
            "a construction receipt must state the decision-time rule its columns respect")
    return {"decision_time_rule": decision_time_rule.strip(),
            "per_row_decision_time_column": per_row_decision_time_column,
            "fold_cutoff": None if fold_cutoff is None else str(fold_cutoff),
            "target_cutoff": None if target_cutoff is None else str(target_cutoff),
            "notes": notes}


def fold_declaration(*, fold_id: str, kind: str, n_rows: int,
                     first_decision_time: Any = None, last_decision_time: Any = None,
                     train_selector: str | None = None, test_selector: str | None = None,
                     n_test_rows: int | None = None) -> dict:
    """The chronological fold this construction is for. ``kind`` is ``fold`` or ``final_design``."""
    if not (isinstance(fold_id, str) and fold_id.strip()):
        raise ConstructionReceiptFailure("a construction receipt must name its fold")
    if kind not in ("fold", "final_design"):
        raise ConstructionReceiptFailure(f"unknown fold kind {kind!r}")
    return {"fold_id": fold_id.strip(), "kind": kind, "n_rows": int(n_rows),
            "first_decision_time": None if first_decision_time is None else str(first_decision_time),
            "last_decision_time": None if last_decision_time is None else str(last_decision_time),
            "train_selector": train_selector, "test_selector": test_selector,
            "n_test_rows": None if n_test_rows is None else int(n_test_rows)}


# --------------------------------------------------------------------------------------------
# the receipt's own binding
# --------------------------------------------------------------------------------------------

#: exactly the facts a construction receipt is bound to. Volatile fields (wall-clock time, the
#: absolute path the receipt was written to) are deliberately excluded: two runs of the same
#: producer over the same bytes for the same fold ARE the same construction and must digest alike.
def binding_fields(receipt: Mapping[str, Any]) -> dict:
    ident = dict(receipt.get("identity") or {})
    prod = dict((receipt.get("produced_frame_provenance") or {}))
    frozen = dict((receipt.get("frozen_source_provenance") or {}))
    producer = dict(prod.get("producer") or {})
    commit = dict(prod.get("commit") or {})
    universe = dict(prod.get("universe") or {})
    fold = dict(prod.get("fold") or {})
    feats = dict(prod.get("features") or {})
    frame = dict(prod.get("raw_frame") or {})
    miss = dict(frame.get("missingness") or {})
    return {
        "schema": receipt.get("schema"),
        "receipt_kind": receipt.get("receipt_kind"),
        "experiment": ident.get("experiment"),
        "arm": ident.get("arm"),
        "fold": ident.get("fold"),
        "scope": ident.get("scope"),
        "run_id": ident.get("run_id"),
        "run_uid": ident.get("run_uid"),
        "producer_source_sha256": producer.get("source_sha256"),
        "producer_source_name": (Path(producer["source_path"]).name
                                 if producer.get("source_path") else None),
        "producing_commit": commit.get("sha"),
        "universe_contract_id": universe.get("universe_contract_id"),
        "row_universe_digest": universe.get("row_universe_digest"),
        "row_order_digest": universe.get("row_order_digest"),
        "feature_set_id": feats.get("feature_set_id"),
        "feature_order_digest": feats.get("feature_order_digest"),
        "feature_name_membership_digest": feats.get("feature_name_membership_digest"),
        "raw_frame_values_digest": frame.get("values_digest"),
        "raw_frame_row_identity_digest": frame.get("row_identity_digest"),
        "raw_missingness_digest": miss.get("aggregate_digest"),
        "per_column_missingness_digests": {
            c: v.get("missing_mask_digest")
            for c, v in sorted((miss.get("per_column") or {}).items())},
        "cutoff_contract": prod.get("cutoff"),
        "fold_identity": {k: fold.get(k) for k in sorted(fold)},
        "transformation_digest": prod.get("transformation_digest"),
        "gate_argument_digests": prod.get("gate_argument_digests"),
        "output": prod.get("output"),
        "generation_result": prod.get("generation", {}).get("result"),
        "source_manifest": [
            {"path": s.get("path"), "sha256": s.get("sha256"), "role": s.get("role"),
             "cutoff_valid": s.get("cutoff_valid")}
            for s in (frozen.get("sources") or [])],
    }


def receipt_digest(fields: Mapping[str, Any]) -> str:
    return "construction:sha256=" + hashlib.sha256(
        _canonical({k: fields[k] for k in sorted(fields)}).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------
# emission -- called BY THE PRODUCER, DURING construction
# --------------------------------------------------------------------------------------------

def emit_construction_receipt(*, receipt_path: str | Path,
                              experiment: str, arm: str, fold: str, run_id: str,
                              frame: pd.DataFrame, feature_names: Sequence[str],
                              universe: Mapping[str, Any],
                              fold_identity: Mapping[str, Any],
                              cutoff: Mapping[str, Any],
                              sources: Sequence[Mapping[str, Any]],
                              scope: str = "fold",
                              feature_set_id: str = "",
                              transformation: Mapping[str, Any] | None = None,
                              gate_arguments: Mapping[str, Any] | None = None,
                              output: Mapping[str, Any] | None = None,
                              generation_result: str = "ok",
                              failure: Mapping[str, Any] | None = None,
                              producer_path: str | Path | None = None,
                              repo_root: str | Path | None = None,
                              claim_boundary_additions: Mapping[str, str] | None = None,
                              notes: Mapping[str, Any] | None = None) -> dict:
    """Emit and WRITE the construction receipt for one frame. Returns the receipt dict.

    Call this from inside the producer, with the frame object in hand, before the frame is handed
    to anything. It raises ``ConstructionReceiptFailure`` rather than returning a receipt that
    cannot be shown to describe a real construction, and it raises if the file cannot be written:
    a producer that cannot archive its own construction record has not produced a frame.
    """
    for key, val in (("experiment", experiment), ("arm", arm), ("fold", fold), ("run_id", run_id)):
        if not (isinstance(val, str) and val.strip()):
            raise ConstructionReceiptFailure(
                f"{key} is mandatory; a construction that cannot be filed against an experiment, "
                f"an arm, a fold and a run identifies nothing")
    if scope not in ("fold", "final_design"):
        raise ConstructionReceiptFailure(f"unknown scope {scope!r}")
    if generation_result not in GENERATION_RESULTS:
        raise ConstructionReceiptFailure(f"unknown generation_result {generation_result!r}")
    if generation_result == "failed" and not failure:
        raise ConstructionReceiptFailure(
            "a failed construction must record its failure state; 'it failed' is not a record")
    if not isinstance(frame, pd.DataFrame):
        raise ConstructionReceiptFailure("the constructed frame must be a pandas DataFrame")
    names = [str(c) for c in feature_names]
    if len(set(names)) != len(names):
        raise ConstructionReceiptFailure("duplicate feature names in the declared feature set")
    absent = [c for c in names if c not in frame.columns]
    if absent:
        raise ConstructionReceiptFailure(
            f"declared features are absent from the constructed frame: {absent}")
    if isinstance(frame.index, pd.RangeIndex) or frame.index.equals(pd.RangeIndex(len(frame))):
        raise ConstructionReceiptFailure(
            "the constructed frame carries a positional 0..n-1 index. A row NUMBER is not a row "
            "IDENTITY, and a receipt indexed on row numbers cannot prove which rows it is about")
    if frame.index.has_duplicates:
        raise ConstructionReceiptFailure("the constructed frame has duplicate row labels")
    if not sources:
        raise ConstructionReceiptFailure(
            "a construction with no declared source artifacts is a frame from nowhere")
    for s in sources:
        if not isinstance(s, Mapping) or "sha256" not in s or "role" not in s:
            raise ConstructionReceiptFailure(
                "every source must be built with source_declaration(); a hand-written source "
                "mapping is the caller-manufactured provenance this module exists to replace")
        if s.get("sha256") is None:
            raise ConstructionReceiptFailure(f"source {s.get('path')!r} was unreadable")
    if not isinstance(universe, Mapping) or "row_universe_digest" not in universe:
        raise ConstructionReceiptFailure("universe must be built with universe_contract()")
    if not isinstance(cutoff, Mapping) or "decision_time_rule" not in cutoff:
        raise ConstructionReceiptFailure("cutoff must be built with cutoff_contract()")
    if not isinstance(fold_identity, Mapping) or "fold_id" not in fold_identity:
        raise ConstructionReceiptFailure("fold_identity must be built with fold_declaration()")
    if str(fold_identity.get("fold_id")) != str(fold):
        raise ConstructionReceiptFailure(
            f"fold identity {fold_identity.get('fold_id')!r} contradicts fold {fold!r}")

    producer = producer_identity(producer_path)
    if not producer.get("source_sha256"):
        raise ConstructionReceiptFailure(
            "the producer's own source could not be hashed, so the receipt cannot say which "
            "implementation constructed the frame")
    commit = producing_commit(repo_root)

    prof = missingness_profile(frame, names)
    raw_block = {
        "n_rows": int(len(frame)),
        "n_columns": int(frame.shape[1]),
        "columns": [str(c) for c in frame.columns],
        "columns_digest": digest_of([str(c) for c in frame.columns], "columns"),
        "values_digest": matrix_digest(frame, names),
        "full_frame_digest": values_digest(frame, label="constructed_frame"),
        "row_identity_digest": index_digest(frame.index, label="raw_index"),
        "row_membership_digest": index_digest(frame.index, sort=True, label="raw_index_membership"),
        "index_name": str(frame.index.name) if frame.index.name is not None else None,
        "missingness": prof,
    }
    feats = {
        "feature_set_id": str(feature_set_id),
        "names": names,
        "n_features": len(names),
        "feature_order_digest": digest_of(names, "feature_order"),
        "feature_name_membership_digest": digest_of(sorted(names), "feature_names"),
    }
    gate_arg_digests: dict[str, str | None] | None = None
    if gate_arguments:
        gate_arg_digests = {}
        for k in sorted(gate_arguments):
            v = gate_arguments[k]
            gate_arg_digests[k] = None if v is None else values_digest(v, label=f"{k}_values")

    transformation_digest = (None if transformation is None else
                             "transformation:sha256=" + hashlib.sha256(
                                 _canonical(transformation).encode("utf-8")).hexdigest())

    if universe.get("row_universe_digest") != raw_block["row_membership_digest"]:
        raise ConstructionReceiptFailure(
            "the constructed frame's row universe is not the declared universe contract's. The "
            "shared universe is what makes incumbent, K0 and challenger constructions comparable; "
            "a frame that silently drew different rows is refused here")

    run_uid = hashlib.sha256("|".join([
        str(experiment), str(arm), str(fold), str(scope), str(run_id),
        str(producer.get("source_sha256")), str(raw_block["values_digest"]),
        str(universe.get("row_universe_digest"))]).encode("utf-8")).hexdigest()[:32]

    boundary = dict(CLAIM_BOUNDARY)
    boundary.update({k: str(v) for k, v in dict(claim_boundary_additions or {}).items()
                     if k not in CLAIM_BOUNDARY})

    receipt: dict[str, Any] = {
        "schema": CONSTRUCTION_RECEIPT_SCHEMA,
        "receipt_kind": "feature_construction",
        "claim_boundary": boundary,
        "identity": {"experiment": str(experiment), "arm": str(arm), "fold": str(fold),
                     "scope": scope, "run_id": str(run_id), "run_uid": run_uid},
        "frozen_source_provenance": {
            "block": "PROVENANCE OF THE FROZEN INPUT ARTIFACTS",
            "established_by_this_receipt": False,
            "statement": (
                "these artifacts were produced upstream and are read here READ-ONLY. Their "
                "original construction is attested by their own artifact and validation "
                "receipts, recorded below, and by nothing in this receipt. This block records "
                "WHICH BYTES were read and WHAT the pre-existing receipts say about them"),
            "status": "legacy_receipts_only",
            "n_sources": len(list(sources)),
            "sources": [dict(s) for s in sources],
            "source_manifest_digest": digest_of(
                [f"{s.get('path')}={s.get('sha256')}" for s in sources], "source_manifest"),
        },
        "produced_frame_provenance": {
            "block": "PROVENANCE OF THE FEATURE FRAME THIS PRODUCER EMITTED",
            "established_by_this_receipt": True,
            "statement": (
                "this producer, at this commit, read exactly the bytes named above, drew exactly "
                "this universe, and emitted exactly this frame for exactly this fold"),
            "producer": producer,
            "commit": commit,
            "universe": dict(universe),
            "fold": dict(fold_identity),
            "cutoff": dict(cutoff),
            "features": feats,
            "raw_frame": raw_block,
            "transformation": (dict(transformation) if transformation is not None else None),
            "transformation_digest": transformation_digest,
            "gate_argument_digests": gate_arg_digests,
            "output": (dict(output) if output is not None
                       else {"kind": "frame", "digest": raw_block["values_digest"]}),
            "generation": {"result": generation_result,
                           "failure": (dict(failure) if failure else None)},
        },
        "emitted_utc": _utc(),
        "receipt_path": str(Path(receipt_path)),
        "notes": dict(notes or {}),
        "note": ("a caller naming a matrix 'raw' is a claim; this receipt is what the repository "
                 "can re-derive from disk when that claim is presented"),
    }
    fields = binding_fields(receipt)
    receipt["binding"] = {"receipt_digest": receipt_digest(fields), "fields": fields,
                          "note": "verify_construction_receipt recomputes this from the receipt "
                                  "body and from the files and frame presented"}

    p = Path(receipt_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(receipt, indent=2, default=str), encoding="utf-8")
        back = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConstructionReceiptFailure(
            f"the construction receipt could not be written to {p}: {e!r}. An unwritable "
            f"construction record is a construction failure, not a warning: the frame it "
            f"describes must not be fitted") from e
    if back.get("binding", {}).get("receipt_digest") != receipt["binding"]["receipt_digest"]:
        raise ConstructionReceiptFailure(
            "the construction receipt did not survive its own round trip to disk")
    return receipt


# --------------------------------------------------------------------------------------------
# verification -- from a PATH, re-derived against on-disk reality
# --------------------------------------------------------------------------------------------

def read_construction_receipt(path: str | Path) -> tuple[dict | None, list[dict]]:
    """Read a receipt off disk. Returns ``(receipt_or_None, findings)``; never raises."""
    p = Path(path)
    try:
        body = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [_finding("construction_receipt_absent", path=str(p),
                               detail="no producer construction receipt exists at this path. A "
                                      "frame whose construction was never recorded cannot be "
                                      "shown to have come from any producer")]
    except Exception as e:
        return None, [_finding("construction_receipt_unreadable", path=str(p), error=repr(e),
                               detail="the construction receipt could not be read or parsed")]
    if not isinstance(body, Mapping):
        return None, [_finding("construction_receipt_not_a_mapping", path=str(p),
                               python_type=type(body).__name__)]
    if str(body.get("schema")) != CONSTRUCTION_RECEIPT_SCHEMA:
        return dict(body), [_finding(
            "construction_receipt_schema_unrecognised", path=str(p), schema=body.get("schema"),
            expected=CONSTRUCTION_RECEIPT_SCHEMA,
            detail="this verifier knows one construction-receipt schema; an unrecognised one "
                   "cannot be checked and must not be trusted")]
    return dict(body), []


def verify_construction_receipt(path: str | Path, *,
                                frame: Any = None,
                                feature_names: Sequence[str] | None = None,
                                experiment: str | None = None, arm: str | None = None,
                                fold: str | None = None, scope: str | None = None,
                                universe: Mapping[str, Any] | None = None,
                                cutoff: Mapping[str, Any] | None = None,
                                gate_arguments: Mapping[str, Any] | None = None,
                                fitted_frame: Any = None,
                                require_sources_cutoff_valid: bool = True) -> dict:
    """Re-derive a construction receipt against the files and the frame presented.

    Everything checkable is re-checked from disk: the producer source is re-hashed, every declared
    source artifact is re-hashed, the pre-existing artifact and validation receipts are re-read and
    re-compared against the artifact's current bytes, and every frame digest is recomputed from
    the frame the caller is actually holding. The receipt's own binding digest is recomputed from
    its body, so an edited receipt whose author forgot to re-bind is caught.

    Returns a machine-readable report. ``verified`` is true only when nothing blocks.
    """
    findings: list[dict] = []
    checks: dict[str, Any] = {}
    receipt, read_findings = read_construction_receipt(path)
    findings += read_findings
    if receipt is None or read_findings:
        return {"schema": VERIFICATION_SCHEMA, "receipt_path": str(path), "receipt": receipt,
                "receipt_digest": None, "checks": checks, "findings": findings,
                "blocking": [f for f in findings if f["kind"] in BLOCKING],
                "verified": False}

    prod = dict(receipt.get("produced_frame_provenance") or {})
    frozen = dict(receipt.get("frozen_source_provenance") or {})
    ident = dict(receipt.get("identity") or {})
    producer = dict(prod.get("producer") or {})
    commit = dict(prod.get("commit") or {})
    rec_universe = dict(prod.get("universe") or {})
    rec_feats = dict(prod.get("features") or {})
    rec_frame = dict(prod.get("raw_frame") or {})
    rec_miss = dict(rec_frame.get("missingness") or {})

    # ---- the receipt is a complete document ------------------------------------------------
    required = {"identity": ident, "frozen_source_provenance": frozen,
                "produced_frame_provenance": prod, "producer": producer,
                "universe": rec_universe, "features": rec_feats, "raw_frame": rec_frame,
                "binding": receipt.get("binding")}
    empty = sorted(k for k, v in required.items() if not v)
    if empty:
        findings.append(_finding("construction_receipt_incomplete", missing_blocks=empty,
                                 detail="the receipt does not carry the blocks a construction "
                                        "receipt is defined by"))
        return {"schema": VERIFICATION_SCHEMA, "receipt_path": str(path), "receipt": receipt,
                "receipt_digest": None, "checks": checks, "findings": findings,
                "blocking": [f for f in findings if f["kind"] in BLOCKING], "verified": False}

    # ---- the receipt's own binding -----------------------------------------------------------
    stored_digest = (receipt.get("binding") or {}).get("receipt_digest")
    recomputed = receipt_digest(binding_fields(receipt))
    checks["self_binding"] = bool(stored_digest == recomputed)
    if not checks["self_binding"]:
        findings.append(_finding(
            "construction_receipt_self_binding_broken", stored=stored_digest,
            recomputed=recomputed,
            detail="the receipt's body does not hash to the digest it carries; it was edited "
                   "after emission, or it was assembled by something that is not this module"))

    # ---- the producer ---------------------------------------------------------------------------
    ppath = producer.get("source_path")
    live = _sha256_file(ppath)
    checks["producer_source_readable"] = live is not None
    if live is None:
        findings.append(_finding(
            "producer_source_unreadable", producer_source_path=ppath,
            detail="the producer named by the receipt cannot be read, so the running producer "
                   "cannot be shown to be the one that constructed the frame"))
    else:
        checks["producer_source_digest_matches"] = bool(live == producer.get("source_sha256"))
        if not checks["producer_source_digest_matches"]:
            findings.append(_finding(
                "producer_source_digest_mismatch", producer_source_path=ppath,
                recorded=producer.get("source_sha256"), on_disk=live,
                detail="the producer's source has changed since it emitted this receipt. The "
                       "frame on offer was built by an implementation that no longer exists, and "
                       "no re-derivation can recover which one"))
    if producer.get("resolution") == "explicit":
        findings.append(_finding(
            "producer_resolution_explicit", producer_source_path=ppath,
            detail="the producer path was supplied explicitly rather than resolved from the call "
                   "stack; recorded, and the file is hashed and re-hashed identically either way"))

    checks["producing_commit_recorded"] = bool(commit.get("resolved") and commit.get("sha"))
    if not checks["producing_commit_recorded"]:
        findings.append(_finding(
            "producing_commit_unrecorded", commit=commit,
            detail="the receipt does not record the commit the producer ran at, so the source it "
                   "names cannot be located in history"))
    elif commit.get("worktree_dirty"):
        findings.append(_finding(
            "producing_commit_dirty", commit_sha=commit.get("sha"),
            detail="the worktree carried uncommitted tracked changes when the frame was built. "
                   "Recorded, not blocking: the producer source digest is the load-bearing fact "
                   "and it is re-derived independently"))

    # ---- the frozen sources ------------------------------------------------------------------------
    src_status = []
    for s in list(frozen.get("sources") or []):
        sp = s.get("path")
        live_sha = _sha256_file(sp)
        row = {"path": sp, "role": s.get("role"), "recorded": s.get("sha256"),
               "on_disk": live_sha, "matches": bool(live_sha == s.get("sha256")),
               "cutoff_valid": s.get("cutoff_valid")}
        src_status.append(row)
        if live_sha is None:
            findings.append(_finding(
                "source_artifact_unreadable", path=sp, role=s.get("role"),
                detail="a declared frozen source cannot be read now, so the bytes the frame was "
                       "built from cannot be re-derived"))
            continue
        if not row["matches"]:
            findings.append(_finding(
                "source_artifact_digest_mismatch", path=sp, role=s.get("role"),
                recorded=s.get("sha256"), on_disk=live_sha,
                detail="a frozen source artifact's bytes are not the bytes this construction "
                       "read. The frame on offer is about different inputs than the receipt "
                       "describes"))
        if s.get("cutoff_valid") is None or not isinstance(s.get("cutoff_rationale"), str):
            findings.append(_finding(
                "source_cutoff_validity_undeclared", path=sp,
                detail="every source must declare whether it is cutoff-valid, with a rationale"))
        elif s.get("role") == "feature_source" and s.get("cutoff_valid") is not True and \
                require_sources_cutoff_valid:
            findings.append(_finding(
                "source_not_cutoff_valid_for_features", path=sp,
                detail="a feature source that does not assert cutoff validity is a leak"))
        elif s.get("role") == "outcome_source":
            findings.append(_finding(
                "source_is_outcome_not_feature", path=sp,
                detail="declared as an OUTCOME source: it is not cutoff-valid by definition and "
                       "the receipt asserts it contributes no feature column. Recorded so a "
                       "reader can check that assertion against the feature list"))
        for label in ("artifact_receipt", "validation_receipt"):
            r = s.get(label)
            if not r:
                findings.append(_finding(
                    "frozen_source_receipt_unavailable", path=sp, receipt_kind=label,
                    detail="no pre-existing %s is bound for this frozen source; its upstream "
                           "construction is correspondingly less attested" % label))
                continue
            if r.get("matches_current_artifact_bytes") is False:
                findings.append(_finding(
                    "frozen_source_receipt_stale", path=sp, receipt_kind=label,
                    receipt_path=r.get("path"),
                    recorded_artifact_sha256=r.get("recorded_artifact_sha256"),
                    artifact_sha256_now=live_sha,
                    detail="the pre-existing %s certifies different bytes than the artifact now "
                           "holds. Recorded, not blocking here: this construction binds the bytes "
                           "it actually read, and the staleness of an upstream receipt is an "
                           "upstream fact a reader must see rather than a property of this frame"
                           % label))
    checks["sources"] = src_status
    checks["all_sources_match"] = all(r["matches"] for r in src_status) if src_status else False
    recomputed_manifest = digest_of(
        [f"{s.get('path')}={s.get('sha256')}" for s in (frozen.get("sources") or [])],
        "source_manifest")
    checks["source_manifest_digest_matches"] = bool(
        recomputed_manifest == frozen.get("source_manifest_digest"))
    if not checks["source_manifest_digest_matches"]:
        findings.append(_finding(
            "source_manifest_mismatch", recorded=frozen.get("source_manifest_digest"),
            recomputed=recomputed_manifest,
            detail="the source list does not hash to the manifest digest the receipt records"))

    # ---- generation result ----------------------------------------------------------------------------
    gen = dict(prod.get("generation") or {})
    checks["generation_ok"] = bool(gen.get("result") == "ok")
    if not checks["generation_ok"]:
        findings.append(_finding(
            "construction_failed", generation=gen,
            detail="the producer recorded that this construction FAILED. The receipt exists so "
                   "the failure is archivable; the frame it describes must not be fitted"))

    # ---- identity, fold and cutoff ------------------------------------------------------------------
    want = {"experiment": experiment, "arm": arm, "fold": fold, "scope": scope}
    diverged = {k: (ident.get(k), str(v)) for k, v in want.items()
                if v is not None and str(ident.get(k)) != str(v)}
    checks["identity_matches"] = not diverged
    if diverged:
        findings.append(_finding(
            "fold_identity_mismatch", diverging=diverged,
            detail="this construction receipt was emitted for a different experiment, arm, fold "
                   "or scope than the one it is being presented for. A receipt copied onto "
                   "another fold is evidence about a construction that fold never ran"))
    if cutoff is not None:
        checks["cutoff_matches"] = bool(_canonical(dict(prod.get("cutoff") or {}))
                                        == _canonical(dict(cutoff)))
        if not checks["cutoff_matches"]:
            findings.append(_finding(
                "cutoff_contract_mismatch", recorded=prod.get("cutoff"), presented=dict(cutoff),
                detail="the decision-time contract presented is not the one the frame was built "
                       "under; a receipt cannot be carried across a change of cutoff"))

    # ---- the universe ---------------------------------------------------------------------------------
    if universe is not None:
        checks["universe_contract_id_matches"] = bool(
            str(universe.get("universe_contract_id"))
            == str(rec_universe.get("universe_contract_id")))
        checks["universe_digest_matches"] = bool(
            universe.get("row_universe_digest") == rec_universe.get("row_universe_digest"))
        if not checks["universe_contract_id_matches"] or not checks["universe_digest_matches"]:
            findings.append(_finding(
                "universe_contract_mismatch",
                recorded_contract=rec_universe.get("universe_contract_id"),
                presented_contract=universe.get("universe_contract_id"),
                recorded_digest=rec_universe.get("row_universe_digest"),
                presented_digest=universe.get("row_universe_digest"),
                detail="the shared universe contract presented is not the one this frame was "
                       "drawn from. Incumbent, K0 and challenger constructions are only "
                       "comparable when they name the same universe, and this pair does not"))

    # ---- the frame ------------------------------------------------------------------------------------
    names = ([str(c) for c in feature_names] if feature_names is not None
             else list(rec_feats.get("names") or []))
    if feature_names is not None:
        checks["feature_order_matches"] = bool(
            digest_of(names, "feature_order") == rec_feats.get("feature_order_digest"))
        checks["feature_membership_matches"] = bool(
            digest_of(sorted(names), "feature_names")
            == rec_feats.get("feature_name_membership_digest"))
        if not (checks["feature_order_matches"] and checks["feature_membership_matches"]):
            findings.append(_finding(
                "feature_set_mismatch", recorded=list(rec_feats.get("names") or []),
                presented=names,
                order_matches=checks["feature_order_matches"],
                membership_matches=checks["feature_membership_matches"],
                detail="the declared feature set, or its ORDER, is not the one the producer "
                       "constructed. Every positional consumer downstream is indexed by position"))

    if isinstance(frame, pd.DataFrame):
        got_membership = index_digest(frame.index, sort=True, label="raw_index_membership")
        got_order = index_digest(frame.index, label="raw_index")
        checks["row_universe_matches"] = bool(
            got_membership == rec_frame.get("row_membership_digest"))
        checks["row_order_matches"] = bool(got_order == rec_frame.get("row_identity_digest"))
        if not checks["row_universe_matches"]:
            findings.append(_finding(
                "row_universe_mismatch", recorded=rec_frame.get("row_membership_digest"),
                presented=got_membership, n_rows_recorded=rec_frame.get("n_rows"),
                n_rows_presented=int(len(frame)),
                detail="the frame presented is about a different set of rows than the producer "
                       "constructed. Right shape, wrong rows, is evidence about somebody else's "
                       "universe"))
        elif not checks["row_order_matches"]:
            findings.append(_finding(
                "row_order_mismatch", recorded=rec_frame.get("row_identity_digest"),
                presented=got_order,
                detail="same rows, different order. Every consumer that reads this frame "
                       "positionally would read it against mismatched rows"))
        got_values = matrix_digest(frame, names)
        checks["raw_frame_digest_matches"] = bool(got_values == rec_frame.get("values_digest"))
        if not checks["raw_frame_digest_matches"]:
            findings.append(_finding(
                "raw_frame_digest_mismatch", recorded=rec_frame.get("values_digest"),
                presented=got_values,
                detail="the values of the frame presented are not the values the producer "
                       "emitted. Whatever this frame is, the producer did not construct it"))
        got_miss = missingness_profile(frame, names)
        checks["missingness_digest_matches"] = bool(
            got_miss.get("aggregate_digest") == rec_miss.get("aggregate_digest"))
        if not checks["missingness_digest_matches"]:
            per_rec = dict(rec_miss.get("per_column") or {})
            changed = sorted(c for c, v in got_miss["per_column"].items()
                             if (per_rec.get(c) or {}).get("missing_mask_digest")
                             != v["missing_mask_digest"])
            findings.append(_finding(
                "missingness_digest_mismatch", columns=changed,
                recorded=rec_miss.get("aggregate_digest"),
                presented=got_miss.get("aggregate_digest"),
                detail="the per-column null masks of the frame presented are not the masks the "
                       "producer recorded. A mask that was filled between construction and audit "
                       "is invisible to any check that only ever sees the filled frame"))

    if fitted_frame is not None:
        want_out = dict(prod.get("output") or {})
        got_out = matrix_digest(fitted_frame, names)
        checks["output_digest_matches"] = bool(got_out == want_out.get("digest"))
        if not checks["output_digest_matches"]:
            findings.append(_finding(
                "output_digest_mismatch", recorded=want_out.get("digest"), presented=got_out,
                detail="the frame declared as the producer's output is not the one presented"))

    # ---- the gate arguments the producer also emitted ---------------------------------------------
    rec_args = prod.get("gate_argument_digests")
    if not rec_args:
        findings.append(_finding(
            "no_gate_arguments_declared",
            detail="the producer did not digest the offset, target and outcome mask it emitted "
                   "alongside the frame, so those three remain caller-asserted even though the "
                   "frame does not"))
    elif gate_arguments:
        bad = {}
        for k in sorted(gate_arguments):
            v = gate_arguments[k]
            got = None if v is None else values_digest(v, label=f"{k}_values")
            if k in rec_args and rec_args[k] != got:
                bad[k] = {"recorded": rec_args[k], "presented": got}
        checks["gate_arguments_match"] = not bad
        if bad:
            findings.append(_finding(
                "gate_argument_digest_mismatch", arguments=bad,
                detail="an offset, target or outcome mask presented to the gate is not the one "
                       "the producer emitted with this frame"))

    blocking = [f for f in findings if f["kind"] in BLOCKING]
    if not blocking:
        findings.append(_finding("construction_receipt_verified",
                                 receipt_digest=stored_digest,
                                 detail="every recorded digest re-derived against the files and "
                                        "the frame presented"))
    return {"schema": VERIFICATION_SCHEMA,
            "receipt_path": str(path),
            "receipt_digest": stored_digest,
            "receipt": receipt,
            "identity": ident,
            "claim_boundary": dict(receipt.get("claim_boundary") or {}),
            "checks": checks,
            "findings": findings,
            "blocking": blocking,
            "verified": not blocking}


def require_verified(path: str | Path, **kw: Any) -> dict:
    """``verify_construction_receipt`` that raises instead of reporting. For producers."""
    rep = verify_construction_receipt(path, **kw)
    if not rep["verified"]:
        raise ConstructionReceiptFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


# --------------------------------------------------------------------------------------------

def _main() -> int:                                              # pragma: no cover - descriptive
    print("=" * 94)
    print("construction_receipt — a producer that cannot describe its own construction")
    print("                       has not produced a feature frame")
    print("=" * 94)
    print(f"schema             : {CONSTRUCTION_RECEIPT_SCHEMA}")
    print(f"verification schema: {VERIFICATION_SCHEMA}")
    print(f"blocking kinds     : {len(BLOCKING)}")
    print(f"informational kinds: {len(INFORMATIONAL)}")
    print(f"source roles       : {', '.join(SOURCE_ROLES)}")
    print()
    print("the two blocks, which are NOT the same claim:")
    print("  frozen_source_provenance  established_by_this_receipt = False  (legacy_receipts_only)")
    print("  produced_frame_provenance established_by_this_receipt = True")
    print()
    for k, v in CLAIM_BOUNDARY.items():
        print(f"  {k}:")
        for line in [v[i:i + 84] for i in range(0, len(v), 84)]:
            print(f"      {line}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover
    raise SystemExit(_main())
