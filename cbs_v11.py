"""`contract_baseline_suite_v11` — the canonically-keyed arm.

WHY THIS ARM EXISTS
-------------------

v10 shipped a green Layer-A gate (20/20, 1,266 assertions) over a real player path that could
not execute at all.  `cbs_real_frames_v2.build_player_frame(season, require_attested=True)`
raises::

    MergeError: Merge keys are not unique in left dataset; not a one-to-one merge

for **every season 2021-2026**, not merely for 2024.  `prediction_contract_v3` deliberately
restored dual-team obligations but kept the team-blind `row_uid = pg_uid(player_id, game_id)`,
so the adapter's `(game_id, player_id)` join with `validate="1:1"` cannot complete.  The v10
registration's claim that the adapter builds and hashes real player folds is therefore false;
`contract_baseline_suite_v10__erratum_20260802` records that in the registry.

The gate was green because every v10 suite that touched the player path was synthetic at
precisely the boundary that had changed.  That is the lesson this arm encodes: v11 adds a REAL
no-fit integration check to the standing gate (`tests/test_cbs_real_integration_v11.py`) so a
green gate means the real path executes, not merely that a fixture does.

WHAT CHANGES
------------

1. **One canonical, unique, team-bearing key** — `cbs_obligation_key` (`cbs_obligation_key/1`).
   `row_uid = sha256(player_id, game_id, team_id)`; `player_game_uid = sha256(player_id,
   game_id)` retained for legacy linkage only; `obligation_uid` an explicit alias.  Over the
   35,627 real obligations the canonical key is unique while the legacy key yields 35,613 --
   28 rows sharing 14 ids.
2. **Team-aware obligation joins** — `cbs_real_frames/3` joins master on
   `(game_id, team_id, player_id)` and keys appearance evidence on `(team_id, game_id)`.
3. **A canonical-key-aware validator** — `contract_v4_strict/1`.  The inherited `/3` computed
   coverage over a `row_uid` SET, so one forecast could cover two obligations while two correct
   forecasts were rejected as duplicates.
4. **`cbs_snapshot_manifest/5`** — see `SNAPSHOT_MANIFEST_SCHEMA` below.

WHAT THIS ARM IS NOT
--------------------

**Definition, correction and executability only.  No real MODEL fit, prediction, score,
accuracy result, coverage result, profitability result, or model output exists.**  Real
artifacts ARE read and written, and real frames ARE built and identity-bound — that is the
point of the correction — but nothing is ever handed to an estimator.  "Coverage" throughout
this arm means OBLIGATION COMPLETENESS (did every required row receive a forecast slot), never
predictive accuracy.

The registered `primary_metric` is deliberately `NOT_YET_COMPUTED`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

import cbs_obligation_key as obk
import cbs_provenance_v4 as prov4
import cbs_v10 as _v10
from cbs_identity_v3 import FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE
from cbs_v7 import AdapterBoundaryError, REGISTRY_PATH, canonical_digest, \
    recompute_registered_config_hash as _recompute_for

ARM_ID = "contract_baseline_suite_v11"

#: `cbs_snapshot_manifest/5`, defined in `cbs_provenance_v4`.
#:
#: This is a NEW schema id, not a redefinition of `/4`.  The v4 manifest body carries three
#: fields no genuine v10-era `/4` manifest has — `obligation_key_id`, `membership_rule_id` and
#: `roster_binding_id` — so a checker enforcing them while still calling itself `/4` would be a
#: second contract wearing an existing name.  `/1`-`/4` are REFUSED rather than superseded,
#: following the discipline `cbs_v10` applied to `/1`-`/3`.
SNAPSHOT_MANIFEST_SCHEMA = prov4.SNAPSHOT_MANIFEST_SCHEMA
REJECTED_MANIFEST_SCHEMAS = prov4.REJECTED_MANIFEST_SCHEMAS

#: The registered config digest, recomputed from the registry.
REGISTERED_CONFIG_HASH = \
    "14496612ae8349d27f34866c3fa505aee841fe2a65e242cb4d70f966e03ae378"

SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v11/synthetic-config").hexdigest()


def recompute_registered_config_hash(registry_path: Path | str = REGISTRY_PATH,
                                     *, experiment_id: str = ARM_ID) -> str:
    """SHA-256 over the registry's frozen_config for **this** arm by default."""
    return _recompute_for(registry_path, experiment_id=experiment_id)


# --------------------------------------------------------------------------
# identity
# --------------------------------------------------------------------------

def snapshot_identity(manifest: dict) -> str:
    """Derive the snapshot identity, refusing every pre-`/5` manifest.

    `/4` is refused here for a DIFFERENT reason than `/1`-`/3` were refused by v10: `/4`'s
    frame digests are sound, but a `/4` manifest does not name the obligation key, so it cannot
    demonstrate that the digested rows were uniquely keyed.  A digest over a row set that
    silently collapsed two obligations into one is a faithful digest of the wrong thing.
    """
    if not isinstance(manifest, dict):
        raise AdapterBoundaryError("snapshot manifest must be a mapping")
    schema = manifest.get("schema")
    if schema in REJECTED_MANIFEST_SCHEMAS:
        raise AdapterBoundaryError(
            f"manifest schema {schema!r} is REFUSED by {ARM_ID}: it does not declare an "
            f"obligation key, so its frame digests cannot be shown to describe a uniquely "
            f"keyed row set. Rebuild with {SNAPSHOT_MANIFEST_SCHEMA!r}.")
    if schema != SNAPSHOT_MANIFEST_SCHEMA:
        raise AdapterBoundaryError(
            f"snapshot manifest schema must be {SNAPSHOT_MANIFEST_SCHEMA!r}; got {schema!r}")

    declared = manifest.get("obligation_key_id")
    if declared != obk.OBLIGATION_KEY_ID:
        raise AdapterBoundaryError(
            f"manifest must declare obligation_key_id {obk.OBLIGATION_KEY_ID!r}; "
            f"got {declared!r}")
    if manifest.get("frame_identity_schema") != FRAME_IDENTITY_SCHEMA:
        raise AdapterBoundaryError(
            f"manifest must declare frame_identity_schema {FRAME_IDENTITY_SCHEMA!r}; "
            f"got {manifest.get('frame_identity_schema')!r}")
    if manifest.get("frame_identity_mode") != REAL_PATH_MODE:
        raise AdapterBoundaryError(
            f"manifest must declare frame_identity_mode {REAL_PATH_MODE!r}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise AdapterBoundaryError("snapshot manifest lists no artifacts")
    # exact artifact set is enforced here as well as at construction: a manifest can reach the
    # runner without ever passing through build_snapshot_manifest
    prov4.require_exact_artifact_set(artifacts, where="snapshot manifest at the v11 runner")

    for name, declared in artifacts.items():
        digest = declared["sha256"] if isinstance(declared, dict) else declared
        if not isinstance(digest, str) or len(digest) != 64 or \
                not all(c in "0123456789abcdef" for c in digest.lower()):
            raise AdapterBoundaryError(
                f"snapshot manifest entry {name!r} is not a 64-hex digest")

    frames = manifest.get("frames")
    if not isinstance(frames, dict) or not frames:
        raise AdapterBoundaryError(
            "snapshot manifest declares no frames; the identity must cover the frames "
            "actually consumed, not only the files they came from")
    for name, digest in frames.items():
        if not isinstance(digest, str) or len(digest) != 64 or \
                not all(c in "0123456789abcdef" for c in digest.lower()):
            raise AdapterBoundaryError(
                f"snapshot manifest frame {name!r} is not a 64-hex digest")
    if "captured_at" not in manifest:
        raise AdapterBoundaryError("snapshot manifest has no captured_at")

    return canonical_digest(manifest)


def require_canonical_keys(frames: dict) -> dict:
    """Every non-null player frame must carry a UNIQUE, DECLARED canonical key.

    This is the check whose absence let v10 bind identity to a frame the adapter could not
    even build.  It runs BEFORE any delegation, and it raises rather than de-duplicating:
    silently dropping a duplicate is how `prediction_contract_v2` deleted 14 obligations
    without a receipt.
    """
    checked = {}
    for role, f in frames.items():
        if f is None or not isinstance(f, pd.DataFrame) or "row_uid" not in f.columns:
            continue
        obk.assert_unique_canonical_keys(f, where=f"{ARM_ID} {role} frame")
        if "obligation_key_id" in f.columns:
            declared = set(pd.Series(f["obligation_key_id"]).dropna().unique())
            if declared and declared != {obk.OBLIGATION_KEY_ID}:
                raise AdapterBoundaryError(
                    f"{role} frame declares obligation_key_id {sorted(declared)}, not "
                    f"{obk.OBLIGATION_KEY_ID!r}")
        checked[role] = {"rows": int(len(f)), "distinct_row_uid": int(f["row_uid"].nunique())}
    return checked


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                frames: dict, synthetic: bool,
                                artifact_root: Path | str | None = None,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """Config, snapshot, exact artifact set, artifact bytes, frame identity AND key."""
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v11'} digest {expected_cfg}; got {config_hash!r}")

    if not synthetic:
        recomputed = recompute_registered_config_hash(registry_path)
        if recomputed != REGISTERED_CONFIG_HASH:
            raise AdapterBoundaryError(
                f"the registered config no longer hashes to the bound constant: registry "
                f"recomputes to {recomputed}, module holds {REGISTERED_CONFIG_HASH}")

    if snapshot_manifest is None:
        raise AdapterBoundaryError(
            "snapshot_manifest is mandatory: the snapshot identity is DERIVED, never asserted")

    derived = snapshot_identity(snapshot_manifest)
    if not isinstance(snapshot_hash, str) or snapshot_hash.lower() != derived:
        raise AdapterBoundaryError(
            f"snapshot_hash must equal the identity DERIVED from the manifest ({derived}); "
            f"got {snapshot_hash!r}")

    keys = require_canonical_keys(frames)

    return {"arm_id": ARM_ID, "config_hash": config_hash.lower(),
            "snapshot_hash": derived, "obligation_key_id": obk.OBLIGATION_KEY_ID,
            "snapshot_manifest_schema": SNAPSHOT_MANIFEST_SCHEMA,
            "canonical_keys": keys}


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def _restamp(frame: pd.DataFrame, *, config_hash: str, snapshot_hash: str) -> pd.DataFrame:
    out = frame.copy()
    out["arm_id"] = ARM_ID
    out["config_hash"] = config_hash
    out["data_snapshot_hash"] = snapshot_hash
    return out


def _run(which: str, train, test, fold_id, *, config_hash, snapshot_hash,
         snapshot_manifest=None, universe=None, synthetic=True,
         artifact_root=None, registry_path=REGISTRY_PATH, **kw) -> dict:
    """Bind v11 identity, delegate the MODELLING to v10, re-validate under `/4` strict.

    Same shape as `cbs_v10._run` one level down: the binding runs BEFORE any delegation, so it
    is what stands between a non-uniquely-keyed frame and the fitting code.  Emitted rows are
    restamped to v11's arm and identity and every receipt is recomputed against those values.
    """
    from contract_validator_v4_strict import validate_arm_output_v4

    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    v11_config = identity["config_hash"]
    v11_snapshot = identity["snapshot_hash"]

    shim = {"schema": _v10.SNAPSHOT_MANIFEST_SCHEMA,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "frame_identity_mode": REAL_PATH_MODE,
            "captured_at": snapshot_manifest.get("captured_at"),
            "artifacts": snapshot_manifest["artifacts"]}
    fn = _v10.run_player_fold if which == "player" else _v10.run_team_fold
    out = fn(train, test, fold_id, config_hash=_v10.SYNTHETIC_CONFIG_HASH,
             snapshot_hash=_v10.snapshot_identity(shim), snapshot_manifest=shim,
             universe=universe, synthetic=True, registry_path=registry_path, **kw)

    preds = {t: _restamp(p, config_hash=v11_config, snapshot_hash=v11_snapshot)
             for t, p in out["predictions"].items()}
    sidecar = out["provenance_sidecar"].copy()
    sidecar["arm_id"] = ARM_ID
    sidecar["config_hash"] = v11_config
    sidecar["data_snapshot_hash"] = v11_snapshot

    receipts = dict(out["receipts"])
    prediction = {}
    if universe is not None:
        for target, p in preds.items():
            prediction[target] = validate_arm_output_v4(
                p, universe, target, expected_arm_id=ARM_ID,
                expected_config_hash=v11_config, expected_snapshot_hash=v11_snapshot)
        receipts["prediction_validation"] = {
            "receipt": "prediction_validation/2",
            "validator": "contract_v4_strict/1",
            "ok": all(r["ok"] for r in prediction.values()) and bool(prediction),
            "problems": [f"{t}: {p}" for t, r in prediction.items()
                         for p in r.get("problems", [])],
            "per_target": prediction}

    required = tuple(out["required_receipts"])
    failed = [n for n in required if not receipts.get(n, {}).get("ok")]

    out.update({
        "arm_id": ARM_ID, "predictions": preds, "provenance_sidecar": sidecar,
        "receipts": receipts, "validation_receipts": prediction,
        "failed_receipts": failed,
        "validated": not failed, "scoring_permitted": not failed,
        "snapshot_hash": v11_snapshot, "config_hash": v11_config,
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
    })
    return out


def run_player_fold(train, test, fold_id, **kw) -> dict:
    """All four player targets over CANONICALLY KEYED obligations."""
    return _run("player", train, test, fold_id, **kw)


def run_team_fold(train, test, fold_id, **kw) -> dict:
    """The team target. `test` needs neither `team_points` nor any `ch_*`."""
    return _run("team", train, test, fold_id, **kw)
