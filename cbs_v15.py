#!/usr/bin/env python3
"""cbs_v15.py — the `cbs_v15_player_oof_v5` arm: v14's estimator, v5's population.

**IT DOES NOT CHANGE THE MODEL.** Every estimator, standardizer, selection rule, mask,
calibration, dispersion and emission object is `cbs_v14`'s, imported BY REFERENCE. What changes is
the population being predicted, which is why this is a new arm rather than an amendment.

HOW THE IDENTITY BINDS, AND WHY IT IS NOT CIRCULAR
---------------------------------------------------
`cbs_v14` hard-codes its config digest and recomputes it from the registry to check. That cannot
work here: `/2`'s frozen config must cover the bytes of the implementation, and this file is part
of the implementation, so a hard-coded constant would have to hash itself.

So the binding is inverted and made stronger. `/2`'s frozen config declares a SHA-256 for every
implementation file **except this one's own config value**, and:

  * `REGISTERED_CONFIG_HASH` is recomputed from the registry at import — never transcribed;
  * `verify_implementation_bytes()` re-hashes every declared file **from disk** and refuses if any
    differs, so the arm cannot run against code its registration does not describe.

An arm that cannot prove which implementation it is may not produce rows at all.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cbs_v10 as _v10
import cbs_v14 as _v14
from cbs_v7 import AdapterBoundaryError
from cbs_v7 import recompute_registered_config_hash as _recompute_for

REPO = Path(__file__).resolve().parent

ARM_ID = "cbs_v15_player_oof_v5"
ARM_REVISION = 2
ROW_UNIVERSE = "prediction_contract_v5"
SUPERSEDES = None
INHERITS_ESTIMATOR_FROM = _v14.ARM_ID

ARM_REGISTRY = REPO / "experiments" / "player_program" / "arm_registry.jsonl"
REGISTRY_RECORD_ID = "cbs_v15_player_oof_v5__rev2"

HISTORY_POLICY = "tier_a_target_fit_with_observed_history/1"

#: Inherited by reference. Same objects, so they cannot drift.
snapshot_identity = _v14.snapshot_identity
build_fold_manifest = _v14.build_fold_manifest
sidecar_identity = _v14.sidecar_identity
validate_provenance_sidecar = _v14.validate_provenance_sidecar
verify_artifact_bytes = _v14.verify_artifact_bytes
#: `cbs_v14.require_registered_identity` calls `_v10.bind_frames`; the SAME object is used here so
#: the frame-binding clause cannot differ between the two arms.
bind_frames = _v10.bind_frames
SIDECAR_DIGEST_SCHEMA = _v14.SIDECAR_DIGEST_SCHEMA
PLAYER_TARGETS = _v14.PLAYER_TARGETS

SYNTHETIC_CONFIG_HASH = hashlib.sha256(b"cbs_v15_player_oof_v5/synthetic-config").hexdigest()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def registered_record() -> dict:
    import json
    if not ARM_REGISTRY.exists():
        raise AdapterBoundaryError(f"arm registry not found at {ARM_REGISTRY}")
    rec = None
    for line in ARM_REGISTRY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("experiment_id") == REGISTRY_RECORD_ID:
            rec = obj
    if rec is None:
        raise AdapterBoundaryError(
            f"no registry record for {REGISTRY_RECORD_ID!r}. Register "
            f"cbs_v15_player_oof_v5/2 BEFORE executing: it must carry the implementation hashes.")
    return rec


def recompute_registered_config_hash(registry_path: Path | str = ARM_REGISTRY,
                                     *, experiment_id: str = REGISTRY_RECORD_ID) -> str:
    return _recompute_for(registry_path, experiment_id=experiment_id)


def verify_implementation_bytes(root: Path | str = REPO) -> dict:
    """Every declared implementation file must hash, from disk, to what `/2` registered."""
    root = Path(root)
    frozen = registered_record()["extra"]["frozen_config"]
    declared = frozen.get("implementation_sha256") or {}
    if not declared:
        raise AdapterBoundaryError("the /2 record declares no implementation_sha256")
    problems, checked = [], {}
    for rel, want in sorted(declared.items()):
        p = root / rel
        if not p.exists():
            problems.append(f"{rel}: absent")
            continue
        got = _sha(p)
        checked[rel] = got
        if got != want:
            problems.append(f"{rel}: disk {got[:16]}… != registered {want[:16]}…")
    if problems:
        raise AdapterBoundaryError(
            "the implementation on disk is not the one cbs_v15_player_oof_v5/2 registers: "
            + "; ".join(problems))
    return {"receipt": "implementation_bytes/1", "ok": True,
            "n_files": len(declared), "sha256": checked,
            "why": ("an arm that cannot prove which implementation it is may not produce rows. "
                    "The registration names the bytes; this re-hashes them from disk.")}


try:
    REGISTERED_CONFIG_HASH = recompute_registered_config_hash()
except AdapterBoundaryError:
    #: `/2` is not registered yet. Importing is allowed so the modules can be written and tested;
    #: EXECUTION is not, and `require_registered_identity_v15` refuses below.
    REGISTERED_CONFIG_HASH = None


def require_registered_identity_v15(config_hash: str, snapshot_hash: str,
                                    snapshot_manifest: dict | None, *,
                                    frames: dict, synthetic: bool,
                                    artifact_root: Path | str | None = None,
                                    registry_path: Path | str = ARM_REGISTRY) -> dict:
    """v14's identity clauses, clause for clause, bound to v15's registration.

    Adds one clause v14 has no need of: the implementation bytes on disk must be the ones the
    registration describes.
    """
    if not synthetic:
        impl = verify_implementation_bytes()
        expected_cfg = recompute_registered_config_hash(registry_path)
    else:
        impl, expected_cfg = None, SYNTHETIC_CONFIG_HASH

    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v15'} digest {expected_cfg}; got {config_hash!r}")

    if snapshot_manifest is None:
        raise AdapterBoundaryError(
            "snapshot_manifest is mandatory: the snapshot identity is DERIVED from the artifacts "
            "and frames consumed, never taken on the caller's word")
    derived = snapshot_identity(snapshot_manifest)
    if not isinstance(snapshot_hash, str) or snapshot_hash.lower() != derived:
        raise AdapterBoundaryError(
            f"snapshot_hash {snapshot_hash!r} does not match the identity derived from the "
            f"supplied artifact manifest ({derived})")

    bytes_receipt = None
    if artifact_root is not None:
        bytes_receipt = verify_artifact_bytes(snapshot_manifest, artifact_root)
        if not bytes_receipt["ok"]:
            raise AdapterBoundaryError(
                f"declared artifacts do not match their bytes on disk: "
                f"{bytes_receipt['problems']}")
    elif not synthetic:
        raise AdapterBoundaryError(
            "a real run must supply artifact_root so the declared artifact digests can be "
            "checked against the bytes actually on disk")

    binding = bind_frames(snapshot_manifest, frames)
    if not binding["ok"]:
        raise _v14.FrameBindingError("; ".join(binding["problems"]))

    return {"receipt": "identity_binding/8", "ok": True, "arm_id": ARM_ID,
            "arm_revision": ARM_REVISION, "row_universe": ROW_UNIVERSE,
            "inherits_estimator_from": INHERITS_ESTIMATOR_FROM,
            "history_policy": HISTORY_POLICY,
            "synthetic": bool(synthetic), "config_hash": expected_cfg,
            "config_hash_recomputed_from_registry": expected_cfg,
            "snapshot_hash": derived,
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"]),
            "artifact_bytes": bytes_receipt,
            "implementation_bytes": impl,
            "frame_binding": binding}
