#!/usr/bin/env python3
"""cbs_v10.py — the runner for `contract_baseline_suite_v10`.

v9 is left **byte-untouched**. As at every previous step, the modelling core is
imported and delegated to rather than copied, so the versions cannot drift and a
reader can diff exactly what moved.

WHAT v10 CHANGES
----------------
1. **Frame identity had three remaining domain collisions.** `/2` type-tagged
   scalars correctly but still lost information outside that domain: an
   integer-labelled column was not merely aliased, it was **dropped** — `/2`
   stringified the column list and then reindexed on the stringified names, so a
   column labelled `1` was replaced by an all-NaN column and its values never
   entered the hash at all. Dict keys `1` and `"1"` collided, as did list, tuple
   and ndarray cells. `cbs_frame_identity/3` **rejects before hashing**: string-only
   column labels, scalar-only cells, and no identity at all for a frame outside
   that domain.
2. **The snapshot manifest accepted artifact subsets.** `build_snapshot_manifest`
   could be handed a one-artifact tuple and produce a manifest that
   `cbs_v9.snapshot_identity` accepted, so the "all five inputs are bound" claim
   was true of the documentation and not of the code. `cbs_provenance/3` requires
   **exact key equality** with `CBS_REQUIRED_ARTIFACTS` and rejects subsets and
   supersets alike.
3. **`cbs_snapshot_manifest/4`, and `/1`–`/3` are refused.** The frame-identity
   generation changed, so every earlier manifest's frame digests were computed
   under an encoding that is now known to lose information. Refusing them is the
   same discipline v9 applied to `/2`: a manifest whose identity cannot carry the
   weight now placed on it is not accepted merely because it parses.

The row universe moves too, but not here: the positional candidate lookback was
not availability-causal, and correcting it required a **new contract**
(`prediction_contract_v3`), not a mutation of v2. This runner consumes v3.

**Synthetic only, and structurally so.** No frame arrives from a path. The only
files opened are `experiments/registry.jsonl`, for config identity, and — when an
`artifact_root` is supplied — the snapshot artifacts whose bytes are verified.
Running this module produces no artifact, no accuracy figure and no coverage
score. It neither fits nor predicts on real data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from cbs_identity_v3 import (FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE,
                              FrameIdentityError, frame_digest, frames_digest,
                              require_digestible)
from cbs_v5 import MissingRequiredInput
from cbs_v7 import (AdapterBoundaryError, AvailabilityViolation,
                    DECLARED_CONSTANT_SEASONS, MAX_FALLBACK_LEVEL,
                    OUTCOME_AVAILABILITY_POLICY_ID,
                    OUTCOME_AVAILABILITY_POLICY_LAG_HOURS, OuterFoldViolation,
                    REGISTRY_PATH, canonical_digest,
                    recompute_registered_config_hash as _recompute_for,
                    require_outer_fold)
from cbs_v8 import (FrameBindingError, PLAYER_TARGETS,
                    REQUIRED_PLAYER_FEATURE_SOURCES, REQUIRED_TEAM_FEATURE_SOURCES,
                    SourceProvenanceError, TEAM_CURRENT_OBLIGATION_COLS, TEAM_TARGET,
                    require_team_current_obligations, require_team_history_inputs,
                    verify_artifact_bytes)
from cbs_v5 import TEAM_MIN_PRIOR  # noqa: F401  (re-exported for callers)

ARM_ID = "contract_baseline_suite_v10"

SNAPSHOT_MANIFEST_SCHEMA = "cbs_snapshot_manifest/4"
#: refused outright, not merely superseded — their frame digests were computed
#: under encodings now known to lose information
REJECTED_MANIFEST_SCHEMAS = ("cbs_snapshot_manifest/1", "cbs_snapshot_manifest/2",
                             "cbs_snapshot_manifest/3")

FRAME_BINDING_SCHEMA = "cbs_frame_binding/3"

#: The registered config digest, recomputed from the registry.
REGISTERED_CONFIG_HASH = \
    "46a8e7687b237b1ff01396ad44c6396bafe078568c08dc0f492f7fb8a35ec6f2"

SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v10/synthetic-config").hexdigest()


def recompute_registered_config_hash(registry_path: Path | str = REGISTRY_PATH,
                                     *, experiment_id: str = ARM_ID) -> str:
    """SHA-256 over the registry's frozen_config for **this** arm by default."""
    return _recompute_for(registry_path, experiment_id=experiment_id)


# --------------------------------------------------------------------------
# identity
# --------------------------------------------------------------------------

def snapshot_identity(manifest: dict) -> str:
    """Derive the snapshot identity, refusing every pre-`/4` manifest."""
    if not isinstance(manifest, dict):
        raise AdapterBoundaryError("snapshot manifest must be a mapping")
    schema = manifest.get("schema")
    if schema in REJECTED_MANIFEST_SCHEMAS:
        raise AdapterBoundaryError(
            f"manifest schema {schema!r} is REFUSED: its frame digests were computed "
            f"under a frame-identity encoding now known to lose information — an "
            f"integer-labelled column was dropped rather than hashed, and dict keys "
            f"and container types collided. Rebuild with "
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
    if manifest.get("frame_identity_mode") != REAL_PATH_MODE:
        raise AdapterBoundaryError(
            f"manifest must declare frame_identity_mode {REAL_PATH_MODE!r}; a strict "
            f"container digest and a scalar-only digest are different strings and "
            f"must not be confused")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise AdapterBoundaryError("snapshot manifest lists no artifacts")

    # exact-five is enforced here as well as at construction: a manifest can be
    # handed to the runner without ever passing through build_snapshot_manifest
    from cbs_provenance_v3 import require_exact_artifact_set
    require_exact_artifact_set(artifacts, where="snapshot manifest at the runner")

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
    """Prove the manifest describes THESE frames, under the `/3` domain contract.

    `require_digestible` runs first on every frame, so a frame outside the
    scalar-only/string-column domain is rejected before any digest is computed —
    it gets no identity rather than a weak one.
    """
    declared = manifest.get("frames") or {}
    problems, per_frame = [], {}
    for role, frame in sorted(frames.items()):
        if frame is None:
            continue
        try:
            require_digestible(frame)
        except FrameIdentityError as exc:
            problems.append(f"the {role!r} frame is not digestible: {exc}")
            continue
        if role not in declared:
            problems.append(f"the manifest does not declare the {role!r} frame it "
                            f"was handed")
            continue
        actual = frame_digest(frame, mode=REAL_PATH_MODE)
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
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "frame_identity_mode": REAL_PATH_MODE, "per_frame": per_frame}


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                frames: dict, synthetic: bool,
                                artifact_root: Path | str | None = None,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """Config, snapshot, exact-five artifacts, artifact bytes and frame identity."""
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v10'} digest {expected_cfg}; "
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

    if not synthetic:
        # a manifest built through the test-only escape labels itself; the real
        # path refuses it on those stamps rather than on trust
        from cbs_provenance_v3 import require_real_snapshot_manifest
        require_real_snapshot_manifest(snapshot_manifest)

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

    return {"receipt": "identity_binding/4", "ok": True, "synthetic": bool(synthetic),
            "config_hash": expected_cfg,
            "config_hash_recomputed_from_registry": recomputed,
            "snapshot_hash": derived,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "frame_identity_mode": REAL_PATH_MODE,
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"]),
            "artifact_bytes": bytes_receipt,
            "frame_binding": binding}


# --------------------------------------------------------------------------
# runners — v8's modelling core, bound to the v10 identity and arm
# --------------------------------------------------------------------------

def validate_provenance_sidecar(sidecar: pd.DataFrame, preds: dict, *,
                                fold_id: str, config_hash: str,
                                snapshot_hash: str) -> dict:
    """v8's sidecar validator, with the arm assertion rebound to v10.

    Every clause but the arm identity is v8's and is reused rather than restated;
    a duplicated validator is one that will eventually disagree with itself.
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
    out["digest"] = cbs_v8.sidecar_digest(sidecar)
    return out


def _restamp(frame: pd.DataFrame, *, config_hash: str,
             snapshot_hash: str) -> pd.DataFrame:
    out = frame.copy()
    out["arm_id"] = ARM_ID
    out["config_hash"] = config_hash
    out["data_snapshot_hash"] = snapshot_hash
    return out


def _run(which: str, train, test, fold_id, *, config_hash, snapshot_hash,
         snapshot_manifest=None, universe=None, synthetic=True,
         artifact_root=None, registry_path=REGISTRY_PATH, **kw) -> dict:
    """Bind identity under the v10 rules, delegate the MODELLING, re-validate.

    The order is the point: v10's binding runs before v8's runner is entered, so
    it is what stands between a mutated frame and the fitting code. The emitted
    rows are then restamped to v10's arm and identity and **every receipt is
    recomputed against those values** — the re-validation is what makes the
    restamping honest.
    """
    import cbs_v8
    from contract_validator_v3_strict import validate_arm_output_v3

    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    v10_config = identity["config_hash"]
    v10_snapshot = identity["snapshot_hash"]

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

    preds = {t: _restamp(p, config_hash=v10_config, snapshot_hash=v10_snapshot)
             for t, p in out["predictions"].items()}
    sidecar = out["provenance_sidecar"].copy()
    sidecar["arm_id"] = ARM_ID
    sidecar["config_hash"] = v10_config
    sidecar["data_snapshot_hash"] = v10_snapshot

    receipts = dict(out["receipts"])
    receipts["identity_binding"] = identity
    receipts["frame_binding"] = identity["frame_binding"]
    receipts["provenance_history"] = validate_provenance_sidecar(
        sidecar, preds, fold_id=fold_id, config_hash=v10_config,
        snapshot_hash=v10_snapshot)

    prediction: dict = {}
    if universe is not None:
        for tgt, p in preds.items():
            prediction[tgt] = validate_arm_output_v3(
                p, universe, tgt, expected_arm_id=ARM_ID, expected_fold_id=fold_id,
                expected_config_hash=v10_config, expected_snapshot_hash=v10_snapshot)
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
        "snapshot_hash": v10_snapshot, "config_hash": v10_config,
    })
    return out


def run_player_fold(train, test, fold_id, **kw) -> dict:
    """All four player targets. `test` is a frame of CURRENT obligations."""
    return _run("player", train, test, fold_id, **kw)


def run_team_fold(train, test, fold_id, **kw) -> dict:
    """The team target. `test` needs neither `team_points` nor any `ch_*`."""
    return _run("team", train, test, fold_id, **kw)
