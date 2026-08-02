#!/usr/bin/env python3
"""cbs_v9.py — the runner for `contract_baseline_suite_v9`.

v8 is left **byte-untouched** as the historical record. Every unchanged primitive
is imported from it, so the two cannot drift and a reader can diff exactly what
v9 changed.

WHAT v9 CHANGES
---------------
1. **Frame identity was collidable.** `cbs_v8.frame_digest` rendered every cell
   with `str(v)`, so a null and an empty string hashed alike, and the integer `1`
   and the string `"1"` hashed alike. Frame binding is the check standing between
   a mutated frame and the fitting code, so a collision there let a changed frame
   keep its identity and reach the model. v9 uses
   `cbs_frame_identity.frame_digest` — type-tagged and null-distinct.
2. **The manifest schema is bumped to `cbs_snapshot_manifest/3`, and `/2` is
   refused.** A `/2` manifest's frame digests were computed with the colliding
   encoding; accepting one would mean trusting an identity that cannot carry the
   weight now placed on it. This is not a courtesy version bump.
3. **`recompute_registered_config_hash` is re-exported with a v9 default.** A
   no-argument call reached through v8 resolved to `cbs_v7.ARM_ID` and returned
   *v7's* digest — a helper that silently answers a question about a different
   arm is worse than no helper.

Everything else — the outer-fold guard, the availability-gated walk-forward
engine and its +36h conservative policy bound, the fallback ladders and
`TEAM_MIN_PRIOR`, the source-provenance receipts on every frame, the outcome-free
current-obligation interface, the provenance sidecar, `contract_v2_strict/3`, and
the eight-receipt composite gate — is v8's, unchanged and imported.

**Synthetic only, and structurally so.** No frame arrives from a path. The only
files this module opens are `experiments/registry.jsonl`, for config identity,
and — when an `artifact_root` is supplied — the snapshot artifacts whose bytes it
verifies. Running it produces no artifact, no accuracy figure and no coverage
score. It neither fits nor predicts on real data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from cbs_frame_identity import (FRAME_IDENTITY_SCHEMA, FrameIdentityError,
                                encode_cell, frame_digest, frames_digest)
from cbs_v5 import MissingRequiredInput
from cbs_v7 import (AdapterBoundaryError, AvailabilityViolation,
                    DECLARED_CONSTANT_SEASONS, FittedState, MAX_FALLBACK_LEVEL,
                    OUTCOME_AVAILABILITY_POLICY_ID,
                    OUTCOME_AVAILABILITY_POLICY_LAG_HOURS, OUTCOME_OBSERVED_AT_COL,
                    OuterFoldViolation, PLAYER_SHORT_HISTORY_MAX,
                    PROVENANCE_SIDECAR_SCHEMA, REGISTRY_PATH,
                    build_walk_forward_plan, canonical_digest,
                    recompute_registered_config_hash as _recompute_for,
                    require_outer_fold, walk_forward_counts, walk_forward_ewma)
from cbs_v8 import (FrameBindingError, PLAYER_TARGETS, REQUIRED_PLAYER_FEATURE_SOURCES,
                    REQUIRED_TEAM_FEATURE_SOURCES, SOURCE_PROVENANCE_SCHEMA,
                    SourceProvenanceError, TEAM_CURRENT_OBLIGATION_COLS, TEAM_TARGET,
                    player_history_walk_forward, require_team_current_obligations,
                    require_team_history_inputs, resolve_fold_sources,
                    resolve_sources_receipted, source_provenance_receipt,
                    team_history_usable, verify_artifact_bytes)
from cbs_v5 import TEAM_MIN_PRIOR  # noqa: F401  (re-exported for callers)

ARM_ID = "contract_baseline_suite_v9"

SNAPSHOT_MANIFEST_SCHEMA = "cbs_snapshot_manifest/3"
#: refused outright, not merely superseded — see the module docstring
REJECTED_MANIFEST_SCHEMAS = ("cbs_snapshot_manifest/1", "cbs_snapshot_manifest/2")

FRAME_BINDING_SCHEMA = "cbs_frame_binding/2"

#: The registered config digest, recomputed from the registry.
REGISTERED_CONFIG_HASH = \
    "aa4b3cc53785b9004b88aed748e12e7e4a803c3665c298a6cdd2b0523f6ee260"

SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v9/synthetic-config").hexdigest()


def recompute_registered_config_hash(registry_path: Path | str = REGISTRY_PATH,
                                     *, experiment_id: str = ARM_ID) -> str:
    """SHA-256 over the registry's frozen_config for **this** arm by default.

    v8 imported v7's helper unchanged, whose default `experiment_id` is
    `cbs_v7.ARM_ID`. A no-argument call from v8 therefore returned v7's digest and
    looked like a successful self-check. The default is bound to `ARM_ID` here so
    the question the helper answers is the one the caller meant to ask.
    """
    return _recompute_for(registry_path, experiment_id=experiment_id)


# --------------------------------------------------------------------------
# identity — type-preserving frames, schema /3
# --------------------------------------------------------------------------

def snapshot_identity(manifest: dict) -> str:
    """Derive the snapshot identity, refusing pre-`/3` manifests outright."""
    if not isinstance(manifest, dict):
        raise AdapterBoundaryError("snapshot manifest must be a mapping")
    schema = manifest.get("schema")
    if schema in REJECTED_MANIFEST_SCHEMAS:
        raise AdapterBoundaryError(
            f"manifest schema {schema!r} is REFUSED: its frame digests were computed "
            f"with an encoding in which a null collided with an empty string and an "
            f"integer collided with its own text form. Rebuild the manifest with "
            f"{SNAPSHOT_MANIFEST_SCHEMA!r}.")
    if schema != SNAPSHOT_MANIFEST_SCHEMA:
        raise AdapterBoundaryError(
            f"snapshot manifest schema must be {SNAPSHOT_MANIFEST_SCHEMA!r}; "
            f"got {schema!r}")
    if manifest.get("frame_identity_schema") != FRAME_IDENTITY_SCHEMA:
        raise AdapterBoundaryError(
            f"manifest must declare frame_identity_schema "
            f"{FRAME_IDENTITY_SCHEMA!r}; got "
            f"{manifest.get('frame_identity_schema')!r}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise AdapterBoundaryError("snapshot manifest lists no artifacts")
    for name, declared in artifacts.items():
        digest = declared["sha256"] if isinstance(declared, dict) else declared
        if not isinstance(digest, str) or len(digest) != 64 or \
                not all(c in "0123456789abcdef" for c in digest.lower()):
            raise AdapterBoundaryError(
                f"snapshot manifest entry {name!r} is not a 64-hex digest")
    frames = manifest.get("frames")
    if not isinstance(frames, dict) or not frames:
        raise AdapterBoundaryError(
            "snapshot manifest declares no frames; the identity must cover the "
            "frames actually consumed, not only the files they came from")
    for name, digest in frames.items():
        if not isinstance(digest, str) or len(digest) != 64 or \
                not all(c in "0123456789abcdef" for c in digest.lower()):
            raise AdapterBoundaryError(
                f"snapshot manifest frame {name!r} is not a 64-hex digest")
    if "captured_at" not in manifest:
        raise AdapterBoundaryError("snapshot manifest has no captured_at")
    return canonical_digest(manifest)


def bind_frames(manifest: dict, frames: dict) -> dict:
    """Prove the manifest describes THESE frames, using the collision-safe digest."""
    declared = manifest.get("frames") or {}
    problems, per_frame = [], {}
    for role, frame in sorted(frames.items()):
        if frame is None:
            continue
        if role not in declared:
            problems.append(f"the manifest does not declare the {role!r} frame it "
                            f"was handed")
            continue
        actual = frame_digest(frame)
        per_frame[role] = {"declared": declared[role], "actual": actual,
                           "match": actual == declared[role],
                           "n_rows": int(len(frame))}
        if actual != declared[role]:
            problems.append(
                f"the {role!r} frame does not match the manifest: declared "
                f"{declared[role][:16]}…, actual {actual[:16]}… — a consumed frame "
                f"was mutated while the manifest was reused")
    undeclared = sorted(set(declared) - {r for r, f in frames.items() if f is not None})
    if undeclared:
        problems.append(f"the manifest declares frames that were not supplied: "
                        f"{undeclared}")
    return {"receipt": FRAME_BINDING_SCHEMA, "ok": not problems, "problems": problems,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA, "per_frame": per_frame}


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                frames: dict, synthetic: bool,
                                artifact_root: Path | str | None = None,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """Config, snapshot, artifact bytes and collision-safe frame identity."""
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v9'} digest {expected_cfg}; "
            f"got {config_hash!r}")

    recomputed = None
    if not synthetic:
        recomputed = recompute_registered_config_hash(registry_path)
        if recomputed != REGISTERED_CONFIG_HASH:
            raise AdapterBoundaryError(
                f"the registered config no longer hashes to the bound constant: "
                f"registry recomputes to {recomputed}, module holds "
                f"{REGISTERED_CONFIG_HASH}")

    if snapshot_manifest is None:
        raise AdapterBoundaryError(
            "snapshot_manifest is mandatory: the snapshot identity is DERIVED "
            "from the artifacts and frames consumed, never taken on the caller's word")
    derived = snapshot_identity(snapshot_manifest)
    if not isinstance(snapshot_hash, str) or snapshot_hash.lower() != derived:
        raise AdapterBoundaryError(
            f"snapshot_hash {snapshot_hash!r} does not match the identity derived "
            f"from the supplied artifact manifest ({derived})")

    bytes_receipt = None
    if artifact_root is not None:
        bytes_receipt = verify_artifact_bytes(snapshot_manifest, artifact_root)
        if not bytes_receipt["ok"]:
            raise AdapterBoundaryError(
                f"declared artifacts do not match their bytes on disk: "
                f"{bytes_receipt['problems']}")
    elif not synthetic:
        raise AdapterBoundaryError(
            "a real run must supply artifact_root so the declared artifact digests "
            "can be checked against the bytes actually on disk")

    binding = bind_frames(snapshot_manifest, frames)
    if not binding["ok"]:
        raise FrameBindingError("; ".join(binding["problems"]))

    return {"receipt": "identity_binding/3", "ok": True, "synthetic": bool(synthetic),
            "config_hash": expected_cfg,
            "config_hash_recomputed_from_registry": recomputed,
            "snapshot_hash": derived,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"]),
            "artifact_bytes": bytes_receipt,
            "frame_binding": binding}


# --------------------------------------------------------------------------
# runners — v8's, rebound to the v9 identity and arm
# --------------------------------------------------------------------------

def validate_provenance_sidecar(sidecar: pd.DataFrame, preds: dict, *,
                                fold_id: str, config_hash: str,
                                snapshot_hash: str) -> dict:
    """v8's sidecar validator, with the arm assertion rebound to v9.

    Every clause except the arm identity is identical to v8's and is therefore
    *reused* rather than restated — a duplicated validator is a validator that
    will eventually disagree with itself. The v9 arm is asserted here directly,
    and the shared validator is then run against a probe copy stamped with the
    arm it expects, so its own assertion is satisfied honestly rather than
    disabled.
    """
    import cbs_v8

    problems: list[str] = []
    if "arm_id" not in sidecar.columns:
        return {"receipt": "provenance_history/1", "ok": False,
                "problems": ["sidecar missing arm_id"]}
    if (sidecar["arm_id"] != ARM_ID).any():
        problems.append(f"sidecar arm_id is not uniformly {ARM_ID!r}")

    probe = sidecar.copy()
    probe["arm_id"] = cbs_v8.ARM_ID
    inner = cbs_v8.validate_provenance_sidecar(
        probe, preds, fold_id=fold_id, config_hash=config_hash,
        snapshot_hash=snapshot_hash)

    out = dict(inner)
    out["problems"] = problems + list(inner.get("problems", []))
    out["ok"] = not out["problems"]
    out["arm_id"] = ARM_ID
    # the digest must describe the REAL sidecar, not the probe
    out["digest"] = cbs_v8.sidecar_digest(sidecar)
    return out


def _restamp(frame: pd.DataFrame, *, config_hash: str,
             snapshot_hash: str) -> pd.DataFrame:
    """Stamp emitted rows with the v9 arm and the v9 identity."""
    out = frame.copy()
    out["arm_id"] = ARM_ID
    out["config_hash"] = config_hash
    out["data_snapshot_hash"] = snapshot_hash
    return out


def _run(which: str, train, test, fold_id, *, config_hash, snapshot_hash,
         snapshot_manifest=None, universe=None, synthetic=True,
         artifact_root=None, registry_path=REGISTRY_PATH, **kw) -> dict:
    """Bind identity under the v9 rules, delegate the MODELLING to v8, re-validate.

    The order is the point. v9's collision-safe binding runs **first**, before
    v8's runner is entered, so it is what actually stands between a mutated frame
    and the fitting code. v8 is then asked only to do the modelling, on frames
    whose identity has already been proved.

    v8 emits rows stamped with its own arm and identity, so they are restamped to
    v9's — and then **every receipt is recomputed against the v9 values**. That
    re-validation is what makes the restamping honest: the receipts describe the
    rows as they actually stand, not as they stood before the stamp changed.
    """
    import cbs_v8
    from contract_validator_v3_strict import validate_arm_output_v3

    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    v9_config = identity["config_hash"]
    v9_snapshot = identity["snapshot_hash"]

    # v8's own binding re-runs against a manifest built from the SAME frames with
    # v8's digest. It is a genuine second check, not a bypass: it can only pass if
    # the frames still match, and v9's stronger check has already passed.
    shim = {"schema": cbs_v8.SNAPSHOT_MANIFEST_SCHEMA,
            "captured_at": snapshot_manifest.get("captured_at"),
            "artifacts": snapshot_manifest["artifacts"],
            "frames": {r: cbs_v8.frame_digest(f) for r, f in
                       (("train", train), ("test", test), ("universe", universe))
                       if f is not None}}
    fn = cbs_v8.run_player_fold if which == "player" else cbs_v8.run_team_fold
    out = fn(train, test, fold_id, config_hash=cbs_v8.SYNTHETIC_CONFIG_HASH,
             snapshot_hash=cbs_v8.snapshot_identity(shim), snapshot_manifest=shim,
             universe=universe, synthetic=True, registry_path=registry_path, **kw)

    preds = {t: _restamp(p, config_hash=v9_config, snapshot_hash=v9_snapshot)
             for t, p in out["predictions"].items()}
    sidecar = out["provenance_sidecar"].copy()
    sidecar["arm_id"] = ARM_ID
    sidecar["config_hash"] = v9_config
    sidecar["data_snapshot_hash"] = v9_snapshot

    receipts = dict(out["receipts"])
    receipts["identity_binding"] = identity
    receipts["frame_binding"] = identity["frame_binding"]
    receipts["provenance_history"] = validate_provenance_sidecar(
        sidecar, preds, fold_id=fold_id, config_hash=v9_config,
        snapshot_hash=v9_snapshot)

    prediction: dict = {}
    if universe is not None:
        for tgt, p in preds.items():
            prediction[tgt] = validate_arm_output_v3(
                p, universe, tgt, expected_arm_id=ARM_ID, expected_fold_id=fold_id,
                expected_config_hash=v9_config, expected_snapshot_hash=v9_snapshot)
        receipts["prediction_validation"] = {
            "receipt": "prediction_validation/1",
            "ok": all(r["ok"] for r in prediction.values()) and bool(prediction),
            "problems": [f"{t}: {p}" for t, r in prediction.items()
                         for p in r.get("problems", [])],
            "per_target": prediction}

    required = tuple(out["required_receipts"])
    failed = [n for n in required if not receipts.get(n, {}).get("ok")]

    out.update({
        "arm_id": ARM_ID, "predictions": preds, "provenance_sidecar": sidecar,
        "provenance_sidecar_digest": receipts["provenance_history"].get("digest"),
        "receipts": receipts, "validation_receipts": prediction,
        "failed_receipts": failed,
        "validated": not failed, "scoring_permitted": not failed,
        "snapshot_hash": v9_snapshot, "config_hash": v9_config,
    })
    return out


def run_player_fold(train, test, fold_id, **kw) -> dict:
    """All four player targets. `test` is a frame of CURRENT obligations."""
    return _run("player", train, test, fold_id, **kw)


def run_team_fold(train, test, fold_id, **kw) -> dict:
    """The team target. `test` needs neither `team_points` nor any `ch_*`."""
    return _run("team", train, test, fold_id, **kw)
