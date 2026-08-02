"""`contract_baseline_suite_v12` — the fit boundary, made executable and fail-closed.

WHY THIS ARM EXISTS
-------------------

`contract_baseline_suite_v11` closed the *frame* boundary: `prediction_contract_v4` gave every
obligation a unique team-bearing key, `cbs_real_frames/3` built all twelve real 2021-2026 folds,
and `tests/test_cbs_real_integration_v11.py` proved the real path runs as far as a bound
`cbs_snapshot_manifest/5`.  The supervisor accepted contract v4 and independently reproduced
every figure in it.

It then rejected v11's *executability* claim one boundary later.  `cbs_v11._run` — the function
that would actually be called by a chronological OOF — is not executable and is not fail-closed:

1. `cbs_v11.require_registered_identity` documents itself as verifying "the real manifest,
   artifact bytes and frame identity" and calls none of `require_real_snapshot_manifest`,
   `verify_artifact_bytes` or `bind_frames`.  It checks manifest *syntax* and key uniqueness.
2. The shim it hands to `cbs_v10.run_*_fold` carries no `frames` member, so the inherited v10
   binder refuses it.
3. After restamping predictions and the provenance sidecar to v11, it copies the inner receipts
   verbatim.  `identity_binding`, `frame_binding` and `provenance_history` therefore describe the
   *synthetic v10* identity and the *pre-restamp* sidecar, and `scoring_permitted` is computed
   from them.
4. Delegation passes `synthetic=True`, which in the inherited player runner defaults
   `allow_declared_defaults=True` and leaves the all-source-absent fallback to a caller-supplied
   `feature_asof` reachable.

Two further defects were measured while implementing the correction, and neither is cosmetic —
each one independently prevents v11's real path from executing at all:

5. **The v11 shim cannot reach the v10 binder in the first place.**  `cbs_v10.snapshot_identity`
   enforces exact artifact-set equality through `cbs_provenance_v3.require_exact_artifact_set`,
   whose `CBS_REQUIRED_ARTIFACTS` names `experiments/prediction_contract_v3/…`.  A v4 manifest
   names `experiments/prediction_contract_v4/…`.  The shim raises `ArtifactSetError` — reported
   as "MISSING 3 required artifact(s) … EXTRA 3" — *before* the missing-`frames` refusal the
   supervisor predicted.  The v10 wrapper is not traversable by a contract-v4 run, and no
   correction confined to the shim's `frames` member would change that.
6. **`cbs_v11._run` calls `validate_arm_output_v4` without `expected_fold_id`**, which that
   function declares keyword-only and required.  Any v11 run supplied with a universe — that is,
   any run that could produce a `prediction_validation` receipt — raises `TypeError` before it
   can produce one.

Running the corrected boundary on real frames then surfaced three more, none of which any
synthetic fixture could have shown.  Two are corrected here; one is a BLOCKER this arm can
diagnose but must not repair on its own authority:

7. **`cbs_v7.canonical_digest` cannot encode a `pandas.Timestamp`, so a real sidecar cannot be
   digested** — and the inherited validator takes that digest in its RETURN statement, after
   every clause, inside a blanket `except Exception`.  On a real sidecar all of its clause
   results are therefore discarded and replaced by one opaque "sidecar validator raised
   TypeError" problem.  Corrected by `cbs_sidecar_identity/2` (see `sidecar_identity`), which is
   a new id rather than a redefinition of `/1`.
8. **The team universe is not keyed by `cbs_obligation_key/1` and cannot be** — that key is
   `sha256(player_id, game_id, team_id)` and a team-game obligation has no player — so
   `contract_v4_strict/1` refuses it for not declaring a key rule.  `require_declared_key=False`
   is the documented flag for exactly this case and waives only the declaration, never
   uniqueness; `require_team_universe_key` discharges the waived obligation explicitly instead
   of leaving it to a bare flag.
9. **BLOCKER, not corrected here: `cbs_generator.order_obligations` is TEAM-BLIND.**  Its tie key
   is `(player_id, season, forecast_cutoff, game_id)`, and `prediction_contract_v4` deliberately
   carries 28 dual-team obligations — 14 pairs, in every season 2021-2026 — that differ only in
   `team_id`.  The guard refuses them as indistinguishable, so **no real player fold can enter
   the modelling core for any season.**  This is the same defect class v11 corrected one layer
   up, surviving at the fit boundary because nothing had ever entered the runner with a real
   frame.  `cbs_generator` and `cbs_v8` are registered and immutable, `run_player_fold` calls the
   function with its default column names, and no seam exists to pass `team_id` or `row_uid`
   through the delegation; correcting it in the project's usual style would mean registering a
   new ordering component AND forking the player runner that calls it, which is the whole
   modelling core and far outside this correction's authorization.  So
   `require_orderable_obligations` fails CLOSED at the v12 boundary with the exact count, the
   affected seasons and the offending canonical keys — and records that adding `team_id` to the
   key resolves all 28 — rather than reordering the frame behind the guard's back.  The real
   TEAM path is unaffected and runs end to end.

WHAT v12 CHANGES, AND WHAT IT DELIBERATELY DOES NOT
---------------------------------------------------

`cbs_v11.py`, `cbs_v10.py`, every earlier arm, and `prediction_contract_v4` are left
**byte-untouched**.  v4 is the row universe; nothing about it is in question.  v12 replaces only
the fit boundary:

* **A per-fold `/5` manifest.**  `build_fold_manifest` builds a `cbs_snapshot_manifest/5` through
  `cbs_provenance_v4` whose `frames` map names the actual `train`, `test` and `universe` frames
  handed to *that* run.  `require_fold_frame_map` then requires the declared roles to be exactly
  the supplied ones, so a manifest describing a different fold cannot be reused.
* **Every real check actually called.**  On the real path `require_registered_identity` calls
  `cbs_provenance_v4.require_real_snapshot_manifest` (the stamps), `cbs_v8.verify_artifact_bytes`
  against a mandatory `artifact_root` (the exact five artifacts' bytes on disk),
  `cbs_v10.bind_frames` (every supplied frame's `cbs_frame_identity/3` digest) and
  `cbs_v11.require_canonical_keys` — all of it before the estimator is reachable.
* **Real-data semantics separated from the legacy identity shim.**  The inherited modelling core
  needs a synthetic identity because its own registered config and artifact set are older
  contracts; that is a fact about `cbs_v8`, not a licence to weaken the real path.  So v12 keeps a
  synthetic *identity* shim — explicitly stamped `real_path_permitted: False` and carrying the
  genuine artifact and frame digests rather than invented ones — while forcing the *data*
  semantics itself: declared Stage-A defaults are passed as `False` and cannot be re-enabled by a
  caller, and `require_real_sources` validates every registered feature-source column on BOTH the
  train and the test frame by calling the per-frame resolver directly, so the
  no-source-columns fallback in `cbs_v8.resolve_fold_sources` is not merely unused but unreachable.
* **Delegation goes to the modelling core, not through the v10 wrapper.**  Defect 5 makes the v10
  wrapper impassable for a contract-v4 manifest, and every check the wrapper contributed —
  `/3` frame identity, the exact artifact set, the real-manifest stamps, the artifact bytes — v12
  performs itself, against the *real* `/5` manifest rather than against a shim.  `cbs_v10` remains
  registered, imported by `cbs_v11`, and unmodified.
* **v12 receipts, recomputed after the restamp.**  `identity_binding/5`, `cbs_frame_binding/3`,
  `cbs_source_provenance/2`, the fold boundary, `provenance_history/2` and
  `prediction_validation/3` are all recomputed against the restamped predictions and sidecar and
  stamped `recomputed_by`.  `validated` and `scoring_permitted` are the conjunction of exactly
  those, and a required receipt that is *not* v12-owned fails the run even if it says `ok`.  The
  inner runner's receipts are retained under `inner_receipts` for audit and take no part in the
  verdict.

WHAT THIS ARM IS NOT
--------------------

**No real MODEL fit, prediction, score, accuracy result, coverage result or profitability result
exists.**  Real artifacts are read, real frames are built and bound, and the real 2021 TEAM fold
is run end to end — but 2021 is the first contracted season, its training window is empty, and
the inherited runner therefore takes its declared-constant path: no estimator is constructed and
nothing is fitted.  `tests/test_cbs_real_integration_v12.py` asserts that with a runtime sentinel.
The real PLAYER fold is blocked before delegation by defect 9 and produces nothing at all.  The
only fitting anywhere in this arm is on synthetic fixtures in `tests/test_cbs_v12.py`.
"Coverage" throughout means OBLIGATION COMPLETENESS — did every owed forecast receive a slot —
never predictive accuracy.

The registered `primary_metric` is deliberately `NOT_YET_COMPUTED`.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from pathlib import Path

import pandas as pd

import cbs_obligation_key as obk
import cbs_provenance_v4 as prov4
import cbs_v8 as _core
import cbs_v10 as _v10
import cbs_v11 as _v11
from cbs_identity_v3 import FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE
from cbs_v7 import (AdapterBoundaryError, REGISTRY_PATH, coverage_receipt,
                    exclusion_receipt, require_outer_fold,
                    recompute_registered_config_hash as _recompute_for)
from cbs_v8 import (FrameBindingError, PLAYER_TARGETS,
                    REQUIRED_PLAYER_FEATURE_SOURCES, REQUIRED_TEAM_FEATURE_SOURCES,
                    SourceProvenanceError, TEAM_TARGET, verify_artifact_bytes)

ARM_ID = "contract_baseline_suite_v12"

#: The row universe is unchanged. v12 corrects a runner, not a contract.
ROW_UNIVERSE = "prediction_contract_v4"

#: `/5` is inherited from `cbs_provenance_v4` unchanged: the manifest CONTRACT is v11's and is
#: not in question. What changes is that v12 actually calls the checks that read it.
SNAPSHOT_MANIFEST_SCHEMA = prov4.SNAPSHOT_MANIFEST_SCHEMA
REJECTED_MANIFEST_SCHEMAS = prov4.REJECTED_MANIFEST_SCHEMAS

IDENTITY_BINDING_SCHEMA = "identity_binding/5"
FRAME_BINDING_SCHEMA = _v10.FRAME_BINDING_SCHEMA          # cbs_frame_binding/3
SOURCE_PROVENANCE_SCHEMA = "cbs_source_provenance/2"
PROVENANCE_HISTORY_SCHEMA = "provenance_history/2"
SIDECAR_DIGEST_SCHEMA = "cbs_sidecar_identity/2"
PREDICTION_VALIDATION_SCHEMA = "prediction_validation/3"
LEGACY_SHIM_ID = "cbs_legacy_identity_shim/1"

#: The roles a fold manifest may name, and the two it must.
FOLD_FRAME_ROLES = ("train", "test", "universe")
REQUIRED_FOLD_FRAME_ROLES = ("train", "test")

#: The tie key `cbs_generator.order_obligations` refuses duplicates on. It is TEAM-BLIND, and
#: `cbs_v8.run_player_fold` calls the function with these defaults, so v12 cannot override them
#: through the delegation. See `require_orderable_obligations`.
INHERITED_ORDERING_KEY = ("player_id", "season", "forecast_cutoff", "game_id")

#: The verdict is the conjunction of exactly these, and each must be v12-owned.
V12_REQUIRED_RECEIPTS = ("identity_binding", "frame_binding", "source_provenance",
                         "fold_boundary", "provenance_history", "prediction_validation",
                         "exclusion_crosstab", "coverage")

#: The registered config digest, recomputed from the registry.
REGISTERED_CONFIG_HASH = \
    "6492c45a479c7794cec5a8afbd8e21ac6d833b2fbda1d6d8a8187252837a1f52"

SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v12/synthetic-config").hexdigest()


def recompute_registered_config_hash(registry_path: Path | str = REGISTRY_PATH,
                                     *, experiment_id: str = ARM_ID) -> str:
    """SHA-256 over the registry's frozen_config for **this** arm by default."""
    return _recompute_for(registry_path, experiment_id=experiment_id)


# --------------------------------------------------------------------------
# identity
# --------------------------------------------------------------------------

def snapshot_identity(manifest: dict) -> str:
    """Derive the snapshot identity under v11's `/5` rules, unchanged.

    Imported rather than restated: two copies of a manifest gate are two gates that will
    eventually disagree, and the `/5` contract itself was accepted by the supervisor. The
    defect v12 corrects is that v11 never *called* the checks that follow this one.
    """
    return _v11.snapshot_identity(manifest)


def require_canonical_keys(frames: dict) -> dict:
    """v11's canonical-key precondition, reused verbatim.

    Its rejection messages name `contract_baseline_suite_v11` because the check is v11's and is
    correct; copying it to relabel the string would fork a guard for cosmetic reasons.
    """
    return _v11.require_canonical_keys(frames)


def require_fold_frame_map(manifest: dict, frames: dict) -> dict:
    """The manifest's frame map must name EXACTLY this fold's frames.

    v11's manifest could legitimately describe *some* frames while the run consumed *others*;
    `snapshot_identity` only checked that each declared digest was 64 hex characters. A per-fold
    manifest is the difference between "these bytes were bound at some point" and "these bytes
    are the ones this fit consumed". `bind_frames` proves the digests match; this proves the
    *set* matches, in both directions, before the digests are compared.
    """
    declared = manifest.get("frames")
    if not isinstance(declared, dict) or not declared:
        raise AdapterBoundaryError("snapshot manifest declares no frames")
    supplied = {r for r, f in frames.items() if f is not None}
    unknown = sorted(set(declared) - set(FOLD_FRAME_ROLES))
    if unknown:
        raise AdapterBoundaryError(
            f"a fold manifest may name only {list(FOLD_FRAME_ROLES)}; it also names {unknown}")
    missing_required = [r for r in REQUIRED_FOLD_FRAME_ROLES if r not in supplied]
    if missing_required:
        raise AdapterBoundaryError(
            f"a fold must supply {list(REQUIRED_FOLD_FRAME_ROLES)}; missing {missing_required}")
    only_declared = sorted(set(declared) - supplied)
    only_supplied = sorted(supplied - set(declared))
    if only_declared or only_supplied:
        raise AdapterBoundaryError(
            f"the snapshot manifest does not describe THIS fold: declared-but-not-supplied "
            f"{only_declared}, supplied-but-not-declared {only_supplied}. A manifest reused "
            f"across folds cannot bind the frames a fit actually consumed.")
    return {"receipt": "fold_frame_map/1", "ok": True,
            "roles": sorted(supplied), "n_frames": len(declared)}


#: The TEAM target is not keyed by `cbs_obligation_key/1` and never could be: that key is
#: `sha256(player_id, game_id, team_id)` and a team-game obligation has no player. Its key is
#: `prediction_contract_v2.tg_uid(team_id, game_id)`, the `tg_` rule, unchanged since v2.
TEAM_KEY_ID = "prediction_contract_v2.tg_uid/1"
TEAM_KEY_PREFIX = "tg_"


def require_team_universe_key(universe) -> dict:
    """The team universe's key must be the `tg_` rule, unique and complete.

    `contract_v4_strict/1` refuses a universe that does not DECLARE `cbs_obligation_key/1`, and
    it is right to: an undeclared key rule cannot be checked. But the team universe deliberately
    does not follow that rule, so v12 passes `require_declared_key=False` for the team target —
    which is the documented use of that flag and not a loosening, because `key_status` still
    enforces uniqueness either way.

    A flag alone would be a quiet exemption, so the obligation the flag waives is discharged
    here instead: the team key must be present, non-null, uniformly `tg_`-prefixed and unique.
    A team universe accidentally carrying player-obligation keys, or a duplicated team-game,
    fails before any estimator is reachable.
    """
    if universe is None:
        raise AdapterBoundaryError("no team universe supplied")
    if "row_uid" not in universe.columns:
        raise AdapterBoundaryError("the team universe has no row_uid")
    key = universe["row_uid"]
    if key.isna().any():
        raise AdapterBoundaryError(
            f"{int(key.isna().sum())} team universe rows have a null row_uid")
    bad = key[~key.astype(str).str.startswith(TEAM_KEY_PREFIX)]
    if len(bad):
        raise AdapterBoundaryError(
            f"{len(bad)} team universe rows do not carry the {TEAM_KEY_PREFIX!r} team-game key "
            f"(e.g. {sorted(bad.astype(str).unique())[:3]}); a player-obligation key in a team "
            f"universe would silently change what is being counted")
    dup = int(key.duplicated(keep=False).sum())
    if dup:
        raise AdapterBoundaryError(
            f"{dup} team universe rows share a team-game key; coverage over a non-unique key "
            f"is undefined")
    declared = universe.get("obligation_key_id")
    if declared is not None and set(pd.Series(declared).dropna().astype(str)) - {TEAM_KEY_ID}:
        raise AdapterBoundaryError(
            f"the team universe declares an obligation_key_id other than {TEAM_KEY_ID!r}")
    return {"receipt": "team_universe_key/1", "ok": True, "recomputed_by": ARM_ID,
            "key_id": TEAM_KEY_ID, "prefix": TEAM_KEY_PREFIX,
            "n_rows": int(len(universe)), "n_distinct_keys": int(key.nunique()),
            "declared_in_frame": declared is not None,
            "why_declaration_is_waived": (
                "cbs_obligation_key/1 is sha256(player_id, game_id, team_id); a team-game "
                "obligation has no player, so the team target cannot follow that rule. "
                "require_declared_key=False waives only the DECLARATION check; uniqueness is "
                "still enforced by contract_v4_strict, and the rule itself is enforced here.")}


class InheritedOrderingCollision(AdapterBoundaryError):
    """The inherited obligation ordering cannot distinguish two canonical obligations."""


def order_collisions(frame) -> dict:
    """Measure, without raising, what the inherited ordering key cannot distinguish.

    Reported as data because the count is the finding: it is exactly the dual-team obligations,
    and it is the same defect class v11 corrected one layer up.
    """
    if frame is None or not len(frame):
        return {"n_rows": 0, "n_colliding_rows": 0, "n_groups": 0, "seasons": {},
                "row_uids": [], "resolved_by_team_id": None}
    missing = [c for c in INHERITED_ORDERING_KEY if c not in frame.columns]
    if missing:
        return {"n_rows": int(len(frame)), "n_colliding_rows": None, "n_groups": None,
                "seasons": {}, "row_uids": [], "resolved_by_team_id": None,
                "not_measurable": f"frame lacks {missing}"}
    key = list(INHERITED_ORDERING_KEY)
    dup = frame.duplicated(subset=key, keep=False)
    hit = frame.loc[dup]
    resolved = None
    if "team_id" in frame.columns:
        resolved = not bool(frame.duplicated(subset=key + ["team_id"], keep=False).any())
    return {
        "n_rows": int(len(frame)),
        "n_colliding_rows": int(dup.sum()),
        "n_groups": int(hit.groupby(key, dropna=False).ngroups) if len(hit) else 0,
        "seasons": ({int(s): int(n) for s, n in hit.groupby("season").size().items()}
                    if len(hit) and "season" in hit.columns else {}),
        "row_uids": (sorted(hit["row_uid"].astype(str))[:32]
                     if "row_uid" in hit.columns else []),
        "ordering_key": key,
        "resolved_by_team_id": resolved,
    }


def require_orderable_obligations(frames: dict) -> dict:
    """Fail closed, and DIAGNOSE, when the inherited ordering key cannot name one obligation.

    `cbs_generator.order_obligations` refuses to proceed when two rows are indistinguishable on
    `(player_id, season, forecast_cutoff, game_id)` — a sound rule, because leaving the order to
    however the frame arrived would make every shifted feature depend on input order. But that
    tuple is TEAM-BLIND, and `prediction_contract_v4` deliberately carries 28 dual-team
    obligations: one player, one game, one cutoff, two clubs, two forecasts owed. They are
    indistinguishable to the guard and identical only in the fields it looks at.

    This is the same defect class v11 corrected one layer up — the team-blind `(game_id,
    player_id)` master join and the `game_id`-keyed appearance index — surviving at the fit
    boundary because nothing had ever entered the runner with a real frame.

    v12 CANNOT repair it in place. `cbs_generator.order_obligations` and `cbs_v8.run_player_fold`
    are both registered and immutable, `run_player_fold` calls the function with its default
    column names, and no seam exists to pass `team_id` or `row_uid` through the delegation.
    Rebinding another module's global would change that module's behaviour for every other
    caller in the process, which `cbs_v8._provenance_rows` already rejects by name as not
    reentrant. Registering a corrected ordering component in the project's usual style would
    also require forking the player runner that calls it, i.e. the whole modelling core — far
    outside this correction's authorization.

    So this raises with the exact count, the affected seasons and the offending canonical keys,
    at the v12 boundary and before any estimator is reachable, rather than surfacing three
    layers down as an opaque `ObligationOrderError`. The measurement, not the workaround, is the
    deliverable: adding `team_id` to the key resolves all 28 rows, and that is recorded so the
    supervisor can rule on how an immutable component should be corrected.
    """
    per_frame, blocked = {}, []
    for role in ("train", "test"):
        rep = order_collisions(frames.get(role))
        per_frame[role] = rep
        if rep.get("n_colliding_rows"):
            blocked.append(role)
    receipt = {"receipt": "inherited_ordering/1", "ok": not blocked,
               "recomputed_by": ARM_ID, "ordering_key": list(INHERITED_ORDERING_KEY),
               "per_frame": per_frame, "blocked_frames": blocked}
    if blocked:
        detail = "; ".join(
            f"{r}: {per_frame[r]['n_colliding_rows']} rows in "
            f"{per_frame[r]['n_groups']} groups across seasons "
            f"{sorted(per_frame[r]['seasons'])}" for r in blocked)
        raise InheritedOrderingCollision(
            f"cbs_generator.order_obligations cannot distinguish two canonical obligations. Its "
            f"tie key {list(INHERITED_ORDERING_KEY)} is TEAM-BLIND, and prediction_contract_v4 "
            f"deliberately carries dual-team obligations that differ only in team_id. {detail}. "
            f"Adding team_id to the key resolves every one of them. cbs_generator and cbs_v8 are "
            f"registered and immutable and expose no seam to pass the column through, so this "
            f"boundary fails CLOSED rather than reordering the frame behind the guard's back. "
            f"Example canonical keys: {per_frame[blocked[0]]['row_uids'][:4]}")
    return receipt


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                frames: dict, synthetic: bool,
                                artifact_root: Path | str | None = None,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """Config, real stamps, per-fold frame map, exact-five bytes, frame digests, and key.

    Every clause below is one v11 documented and did not perform. The order is the point: all of
    it runs before `_run` delegates, so nothing here can be satisfied by a frame that reached an
    estimator first.
    """
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v12'} digest {expected_cfg}; got {config_hash!r}")

    recomputed = None
    if not synthetic:
        recomputed = recompute_registered_config_hash(registry_path)
        if recomputed != REGISTERED_CONFIG_HASH:
            raise AdapterBoundaryError(
                f"the registered config no longer hashes to the bound constant: registry "
                f"recomputes to {recomputed}, module holds {REGISTERED_CONFIG_HASH}")

    if snapshot_manifest is None:
        raise AdapterBoundaryError(
            "snapshot_manifest is mandatory: the snapshot identity is DERIVED, never asserted")

    # (1) the REAL stamps. v11 named this function in its docstring and never called it.
    real_manifest = None
    if not synthetic:
        real_manifest = prov4.require_real_snapshot_manifest(snapshot_manifest)

    fold_map = require_fold_frame_map(snapshot_manifest, frames)

    derived = snapshot_identity(snapshot_manifest)
    if not isinstance(snapshot_hash, str) or snapshot_hash.lower() != derived:
        raise AdapterBoundaryError(
            f"snapshot_hash must equal the identity DERIVED from the manifest ({derived}); "
            f"got {snapshot_hash!r}")

    # (2) the exact five artifacts' BYTES ON DISK.
    bytes_receipt = None
    if artifact_root is not None:
        bytes_receipt = verify_artifact_bytes(snapshot_manifest, artifact_root)
        if not bytes_receipt["ok"]:
            raise AdapterBoundaryError(
                f"declared artifacts do not match their bytes on disk: "
                f"{bytes_receipt['problems']}")
        if bytes_receipt["n_verified"] != prov4.N_REQUIRED_ARTIFACTS:
            raise AdapterBoundaryError(
                f"a real run must verify all {prov4.N_REQUIRED_ARTIFACTS} required artifact "
                f"digests against disk; only {bytes_receipt['n_verified']} were verified")
    elif not synthetic:
        raise AdapterBoundaryError(
            "a real run must supply artifact_root so the declared artifact digests can be "
            "checked against the bytes actually on disk")

    # (3) EVERY supplied frame's cbs_frame_identity/3 digest.
    binding = _v10.bind_frames(snapshot_manifest, frames)
    if not binding["ok"]:
        raise FrameBindingError("; ".join(binding["problems"]))

    # (4) the canonical key, before any estimator is reachable.
    keys = require_canonical_keys(frames)

    return {"receipt": IDENTITY_BINDING_SCHEMA, "ok": True, "arm_id": ARM_ID,
            "recomputed_by": ARM_ID, "synthetic": bool(synthetic),
            "config_hash": expected_cfg,
            "config_hash_recomputed_from_registry": recomputed,
            "snapshot_hash": derived,
            "snapshot_manifest_schema": SNAPSHOT_MANIFEST_SCHEMA,
            "real_snapshot_manifest": real_manifest,
            "fold_frame_map": fold_map,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "frame_identity_mode": REAL_PATH_MODE,
            "obligation_key_id": obk.OBLIGATION_KEY_ID,
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"]),
            "artifact_bytes": bytes_receipt,
            "frame_binding": binding,
            "canonical_keys": keys}


def build_fold_manifest(train, test, universe=None, *, root=prov4.REPO_ROOT,
                        require_attested: bool = True) -> dict:
    """A `/5` manifest over EXACTLY the frames this fold will consume.

    There is no artifact parameter, so none can be misused: the five required inputs come from
    `cbs_provenance_v4` and their digests from the bytes on disk.
    """
    frames = {"train": train, "test": test}
    if universe is not None:
        frames["universe"] = universe
    return prov4.build_snapshot_manifest(frames, root=root,
                                         require_attested=require_attested)


# --------------------------------------------------------------------------
# real feature-source provenance — no synthetic escape exists here
# --------------------------------------------------------------------------

def _empty_frame_source_receipt(frame, source_cols, *, role: str) -> dict:
    """Schema validation for a zero-row frame, stated as exactly what it is.

    Raises on a missing column, because that is a real defect an empty frame can still have.
    The row-level clauses — nulls, unparseable values, a source read at or after its own cutoff —
    are vacuously satisfied over zero rows, and the receipt says `row_level_clauses_vacuous`
    rather than reporting zero violations as though rows had been checked.
    """
    missing = [c for c in source_cols if c not in frame.columns]
    if "forecast_cutoff" not in frame.columns:
        missing.append("forecast_cutoff")
    if missing:
        raise SourceProvenanceError(
            f"{role} frame is empty but must still declare its provenance schema; absent "
            f"columns: {sorted(set(missing))}")
    return {"role": role, "n_rows": 0, "sources": list(source_cols),
            "n_at_cutoff": 0, "n_after_cutoff": 0,
            "min_lead_seconds": None, "max_lead_seconds": None,
            "asof_min": None, "asof_max": None,
            "row_level_clauses_vacuous": True,
            "schema_validated": True,
            "why": ("a cold-start fold has no training rows. Zero rows violated the cutoff rule "
                    "because there were zero rows, which is not the same claim as zero of N "
                    "rows violating it.")}


def require_real_sources(train, test, source_cols, *,
                         role_prefix: str = "") -> tuple[dict, pd.Series]:
    """Validate EVERY registered feature-source column on BOTH frames, as a real path.

    Returns `(receipt, feature_asof_for_the_test_frame)`.

    `cbs_v8.resolve_fold_sources` has three branches, and one of them is an escape: when a
    caller declares itself synthetic and the test frame carries *none* of the registered source
    columns, a declared `feature_asof` column is accepted instead. v11 delegated with
    `synthetic=True`, so that escape was live on its registered real path. Today's real frames
    happen to carry all four columns and would not reach it — but "the current frame shape does
    not exercise the escape" is not the same guarantee as "the escape is unreachable", and the
    registered path must give the second.

    This function calls the per-frame resolver directly, so there is no branch to reach. An
    EMPTY training frame — the cold-start case, 2021 being the first contracted season — is
    still validated for SCHEMA: it must carry every registered source column and the cutoff
    column, and the receipt says so on its face. The inherited resolver cannot be run on an
    empty frame at all (`pd.to_datetime` over zero rows leaves the columns typed as strings and
    the cutoff comparison raises `TypeError`), and the inherited fold-level wrapper responds by
    omitting the role from `frames_validated` entirely. Recording `n_rows: 0` and
    `row_level_clauses_vacuous: True` is the difference between "zero training rows violated the
    cutoff rule" and "the training frame was never looked at".
    """
    source_cols = tuple(source_cols)
    feature_asof, test_receipt = _core.resolve_sources_receipted(
        test, source_cols, role=f"{role_prefix}test")
    if len(train):
        _, train_receipt = _core.resolve_sources_receipted(
            train, source_cols, role=f"{role_prefix}train")
    else:
        train_receipt = _empty_frame_source_receipt(train, source_cols,
                                                    role=f"{role_prefix}train")

    per_frame = {"train": train_receipt, "test": test_receipt}
    problems = []
    for role in ("train", "test"):
        if role not in per_frame:
            problems.append(f"the {role!r} frame's feature sources were never validated")
    if not len(test):
        problems.append("the test frame is empty; there is nothing to predict")

    return {"receipt": SOURCE_PROVENANCE_SCHEMA, "ok": not problems, "problems": problems,
            "recomputed_by": ARM_ID, "arm_id": ARM_ID,
            "frames_validated": sorted(per_frame),
            "sources": list(source_cols),
            "synthetic": False,
            "declared_feature_asof_fallback_reachable": False,
            "train_frame_empty": not len(train),
            "per_frame": per_frame}, feature_asof


# --------------------------------------------------------------------------
# the legacy identity shim — labelled, not disguised
# --------------------------------------------------------------------------

def build_legacy_identity_shim(train, test, universe, *, snapshot_manifest: dict) -> dict:
    """A `cbs_snapshot_manifest/2` document for the inherited modelling core.

    The core's own registered config digest and required artifact set belong to earlier
    contracts, so it cannot be entered on ITS real path by a contract-v4 run; it is entered on
    its synthetic identity path instead. That is an identity concession and nothing more, and
    the document says so on its face: it is stamped `real_path_permitted: False`, so
    `cbs_provenance_v4.require_real_snapshot_manifest` refuses it if it is ever handed to a real
    boundary.

    What it does NOT do is invent anything. The artifact digests are the real ones from the `/5`
    manifest v12 has already verified against disk, and the frame digests are the real frames'
    content under the core's own encoding.
    """
    frames = {r: _core.frame_digest(f) for r, f in
              (("train", train), ("test", test), ("universe", universe)) if f is not None}
    return {
        "schema": _core.SNAPSHOT_MANIFEST_SCHEMA,
        "legacy_identity_shim": LEGACY_SHIM_ID,
        "real_path_permitted": False,
        "synthetic": True,
        "why_not_real": (
            "an identity shim for the inherited modelling core, whose registered config digest "
            "and required artifact set name earlier contracts. The v12 boundary performs the "
            "real-manifest, artifact-byte, frame-digest, canonical-key and feature-source "
            "checks itself, against the /5 manifest, before this shim is built."),
        "bound_by": ARM_ID,
        "outer_snapshot_manifest_schema": snapshot_manifest.get("schema"),
        "captured_at": snapshot_manifest.get("captured_at"),
        "artifacts": snapshot_manifest["artifacts"],
        "frames": frames,
    }


# --------------------------------------------------------------------------
# receipts recomputed against what was actually emitted
# --------------------------------------------------------------------------

def sidecar_identity(sidecar: pd.DataFrame) -> str:
    """`cbs_sidecar_identity/2` — a TOTAL, type-preserving digest of the emitted sidecar.

    The inherited `cbs_v7.sidecar_digest` cannot digest a real one. It renders each cell with
    `str(v)` and hands the result to `cbs_v7.canonical_digest`, whose `_canon` has no encoding
    for `pandas.Timestamp`; the real team sidecar carries datetime-valued `forecast_cutoff` and
    `feature_asof`, so it raises `TypeError: Object of type Timestamp is not JSON serializable`.
    Worse, the inherited validator takes that digest in its RETURN statement, after every clause
    has already been evaluated, inside a blanket `except Exception` — so on a real sidecar all of
    its clause results are discarded and replaced by one opaque "sidecar validator raised"
    problem. Nothing had ever noticed because every sidecar it had been shown was a synthetic
    fixture carrying ISO strings.

    This is a NEW id, not a redefinition: `/1` documents remain valid `/1` documents and are
    simply not `/2`. The shape is `/1`'s — sorted on the natural `(target_key, row_uid)` key so a
    row permutation is not a different artifact, over `SIDECAR_COLS` — with `/1`'s `str(v)`
    replaced by `cbs_identity_v3.encode_cell` in the real-path mode. That is the same total,
    null-distinct, type-tagged encoder `cbs_frame_identity/3` already uses, so a null and the
    empty string, and an integer and its own text, stop sharing a digest here too.
    """
    from cbs_v7 import PROVENANCE_SIDECAR_SCHEMA, SIDECAR_COLS
    from cbs_identity_v3 import encode_cell
    missing = [c for c in SIDECAR_COLS if c not in sidecar.columns]
    if missing:
        raise AdapterBoundaryError(f"cannot digest a sidecar missing {missing}")
    d = sidecar.sort_values(["target_key", "row_uid"], kind="mergesort")
    rows = [[encode_cell(v, mode=REAL_PATH_MODE) for v in rec]
            for rec in d[list(SIDECAR_COLS)].astype(object).to_numpy().tolist()]
    payload = {"schema": SIDECAR_DIGEST_SCHEMA, "mode": REAL_PATH_MODE,
               "sidecar_schema": PROVENANCE_SIDECAR_SCHEMA,
               "columns": list(SIDECAR_COLS), "n_rows": int(len(d)), "rows": rows}
    import json as _json
    return hashlib.sha256(_json.dumps(payload, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()


def _digest_safe(frame: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Render datetime-valued cells as ISO-8601 text so the inherited digest cannot raise.

    Applied ONLY to the probe handed to the inherited validator, and to the prediction copies
    handed alongside it, never to anything this arm returns. It is verdict-preserving for every
    clause that reads these columns: the inherited validator compares sidecar against prediction
    with `.astype(str)` on both sides, and `Timestamp.isoformat` is injective, so applying it to
    both sides maps equal values to equal text and unequal values to unequal text. The columns
    it touched are reported in the receipt rather than left for a reader to infer.
    """
    out, touched = frame.copy(), []
    for col in out.columns:
        s = out[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            out[col] = s.map(lambda v: None if pd.isna(v) else pd.Timestamp(v).isoformat())
            touched.append(str(col))
        elif s.dtype == object and s.map(
                lambda v: isinstance(v, (pd.Timestamp, _dt.datetime, _dt.date))).any():
            out[col] = s.map(lambda v: pd.Timestamp(v).isoformat()
                             if isinstance(v, (pd.Timestamp, _dt.datetime, _dt.date))
                             else v)
            touched.append(str(col))
    return out, sorted(touched)


def validate_provenance_sidecar(sidecar: pd.DataFrame, preds: dict, *,
                                fold_id: str, config_hash: str,
                                snapshot_hash: str) -> dict:
    """The inherited sidecar validator, rebound to the v12 arm and run POST-restamp.

    v11 restamped the sidecar and then reported the inner runner's `provenance_history`, which
    had been computed against the pre-restamp rows. This runs the clauses against the rows that
    are actually returned, and the digest it reports is the digest of those rows.

    The inherited clauses hardcode their own arm id, so they are run against a PROBE whose
    `arm_id` column is substituted — the same technique `cbs_v10` uses, and for the same reason:
    temporarily reassigning another module's global is not reentrant. The probe is therefore a
    different document from the emitted sidecar and has a different digest. Both are reported,
    the receipt says which one it names, and the substitution is proved to be confined to that
    single column rather than asserted to be.
    """
    problems: list[str] = []
    for col in ("arm_id", "config_hash", "data_snapshot_hash"):
        if col not in sidecar.columns:
            return {"receipt": PROVENANCE_HISTORY_SCHEMA, "ok": False,
                    "recomputed_by": ARM_ID, "arm_id": ARM_ID,
                    "problems": [f"sidecar missing {col}"]}
    if (sidecar["arm_id"] != ARM_ID).any():
        problems.append(f"sidecar arm_id is not uniformly {ARM_ID!r}")

    # the emitted PREDICTIONS must carry the same identity the receipt is about
    for tgt, p in preds.items():
        for col, want in (("arm_id", ARM_ID), ("config_hash", config_hash),
                          ("data_snapshot_hash", snapshot_hash)):
            if col not in p.columns:
                problems.append(f"{tgt}: emitted predictions carry no {col}")
            elif (p[col].astype(str) != str(want)).any():
                problems.append(f"{tgt}: emitted predictions do not carry the run's {col}")
    for col, want in (("config_hash", config_hash), ("data_snapshot_hash", snapshot_hash)):
        if (sidecar[col].astype(str) != str(want)).any():
            problems.append(f"sidecar {col} is not uniformly the run's value")

    probe, normalised = _digest_safe(sidecar)
    probe["arm_id"] = _core.ARM_ID
    probe_preds = {t: _digest_safe(p)[0] for t, p in preds.items()}

    allowed = {"arm_id", *normalised}
    drifted = [c for c in sidecar.columns
               if c not in allowed and not sidecar[c].astype(str).equals(probe[c].astype(str))]
    if drifted:
        problems.append(f"the legacy validation probe differs from the emitted sidecar in "
                        f"columns other than {sorted(allowed)}: {drifted}")

    inner = _core.validate_provenance_sidecar(
        probe, probe_preds, fold_id=fold_id, config_hash=config_hash,
        snapshot_hash=snapshot_hash)

    out = dict(inner)
    out["problems"] = problems + list(inner.get("problems", []))
    out["receipt"] = PROVENANCE_HISTORY_SCHEMA
    out["arm_id"] = ARM_ID
    out["recomputed_by"] = ARM_ID
    out["inherited_clause_set"] = "provenance_history/1"
    out["digest"] = sidecar_identity(sidecar)
    out["digest_schema"] = SIDECAR_DIGEST_SCHEMA
    out["digest_names"] = "the restamped sidecar this run returns, untouched"
    out["legacy_probe_digest"] = inner.get("digest")
    out["legacy_probe_digest_schema"] = "cbs_sidecar_digest/1"
    out["probe_substituted_columns"] = sorted(allowed)
    out["probe_note"] = (
        "the inherited clauses hardcode their own arm id and their digest cannot encode a "
        "Timestamp, so they are run on a probe with arm_id substituted and datetime cells "
        "rendered as ISO-8601 text — the same rendering applied to the prediction copies, so "
        "every cross-frame comparison stays verdict-identical. `legacy_probe_digest` is the "
        "digest OF THAT PROBE and is not the emitted artifact's identity; `digest` is.")
    out["ok"] = not out["problems"]
    return out


def _restamp(frame: pd.DataFrame, *, config_hash: str, snapshot_hash: str) -> pd.DataFrame:
    out = frame.copy()
    out["arm_id"] = ARM_ID
    out["config_hash"] = config_hash
    out["data_snapshot_hash"] = snapshot_hash
    return out


def _no_universe(name: str) -> dict:
    return {"receipt": name, "ok": False, "recomputed_by": ARM_ID,
            "problems": ["no universe supplied; this receipt cannot be produced, so it does "
                         "not pass"]}


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def _run(which: str, train, test, fold_id, *, config_hash, snapshot_hash,
         snapshot_manifest=None, universe=None, synthetic=True,
         artifact_root=None, registry_path=REGISTRY_PATH, **kw) -> dict:
    """Bind the v12 identity, validate the real sources, delegate, then re-receipt everything."""
    from contract_validator_v4_strict import validate_arm_output_v4

    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    cfg, snap = identity["config_hash"], identity["snapshot_hash"]

    # the fold boundary, recomputed here so it too is a v12 pre-fit check rather than an
    # inherited report
    fold = dict(require_outer_fold(train, test, fold_id))
    fold["recomputed_by"] = ARM_ID
    fold.setdefault("receipt", "fold_boundary/1")
    fold["ok"] = bool(fold.get("ok", True))

    sources = (REQUIRED_PLAYER_FEATURE_SOURCES if which == "player"
               else REQUIRED_TEAM_FEATURE_SOURCES)
    src_receipt, _feature_asof = require_real_sources(train, test, sources)
    if not src_receipt["ok"]:
        raise SourceProvenanceError("; ".join(src_receipt["problems"]))

    # The team target is keyed by the `tg_` team-game rule, not by cbs_obligation_key/1. The
    # declaration check is waived for it, and the rule is enforced here instead.
    require_declared_key = which == "player"
    team_key = (require_team_universe_key(universe)
                if which == "team" and universe is not None else None)

    # The inherited ordering guard is team-blind. Only the player runner calls it, and it does
    # so with its default column names, so this must be diagnosed here or not at all.
    ordering = ({"receipt": "inherited_ordering/1", "ok": True, "recomputed_by": ARM_ID,
                 "not_applicable": "cbs_v8.run_team_fold does not call order_obligations"}
                if which != "player" else
                require_orderable_obligations({"train": train, "test": test}))

    inner_kw = dict(kw)
    if which == "player":
        if inner_kw.pop("allow_declared_defaults", False):
            raise AdapterBoundaryError(
                "declared Stage-A defaults are forbidden by this arm and cannot be re-enabled "
                "by a caller; every registered input must actually be supplied")
        inner_kw["allow_declared_defaults"] = False
    elif "allow_declared_defaults" in inner_kw:
        raise AdapterBoundaryError(
            "the team runner takes no allow_declared_defaults argument; passing one would be "
            "silently ignored rather than honoured")

    shim = build_legacy_identity_shim(train, test, universe,
                                      snapshot_manifest=snapshot_manifest)
    fn = _core.run_player_fold if which == "player" else _core.run_team_fold
    out = fn(train, test, fold_id, config_hash=_core.SYNTHETIC_CONFIG_HASH,
             snapshot_hash=_core.snapshot_identity(shim), snapshot_manifest=shim,
             universe=universe, synthetic=True, registry_path=registry_path, **inner_kw)

    preds = {t: _restamp(p, config_hash=cfg, snapshot_hash=snap)
             for t, p in out["predictions"].items()}
    sidecar = out["provenance_sidecar"].copy()
    sidecar["arm_id"] = ARM_ID
    sidecar["config_hash"] = cfg
    sidecar["data_snapshot_hash"] = snap

    inner_receipts = dict(out["receipts"])
    receipts = dict(inner_receipts)
    receipts["identity_binding"] = identity
    receipts["frame_binding"] = dict(identity["frame_binding"], recomputed_by=ARM_ID)
    receipts["source_provenance"] = src_receipt
    receipts["fold_boundary"] = fold
    # a pre-fit GATE, not a reported verdict: it raises before delegation rather than returning
    # ok=False, so a run that reaches here has already passed it
    receipts["inherited_ordering"] = ordering
    receipts["provenance_history"] = validate_provenance_sidecar(
        sidecar, preds, fold_id=fold_id, config_hash=cfg, snapshot_hash=snap)

    prediction: dict = {}
    if universe is not None:
        for tgt, p in preds.items():
            prediction[tgt] = validate_arm_output_v4(
                p, universe, tgt, expected_arm_id=ARM_ID, expected_fold_id=fold_id,
                expected_config_hash=cfg, expected_snapshot_hash=snap,
                require_declared_key=require_declared_key)
        receipts["prediction_validation"] = {
            "receipt": PREDICTION_VALIDATION_SCHEMA, "recomputed_by": ARM_ID,
            "validator": "contract_v4_strict/1",
            "require_declared_key": require_declared_key,
            "key_rule": (obk.OBLIGATION_KEY_ID if which == "player" else TEAM_KEY_ID),
            "team_universe_key": team_key,
            "ok": all(r["ok"] for r in prediction.values()) and bool(prediction),
            "problems": [f"{t}: {p}" for t, r in prediction.items()
                         for p in r.get("problems", [])],
            "per_target": prediction}
        receipts["coverage"] = dict(coverage_receipt(preds, universe), recomputed_by=ARM_ID)
        receipts["exclusion_crosstab"] = dict(exclusion_receipt(preds, universe),
                                              recomputed_by=ARM_ID)
    else:
        for name in ("prediction_validation", "coverage", "exclusion_crosstab"):
            receipts[name] = _no_universe(name)

    failed = [n for n in V12_REQUIRED_RECEIPTS if not receipts.get(n, {}).get("ok")]
    # A receipt that passes but was inherited is not evidence about THIS arm. v11's verdict was
    # computed from receipts describing the synthetic v10 identity and the pre-restamp sidecar;
    # this clause is what makes that impossible rather than merely unlikely.
    inherited = [n for n in V12_REQUIRED_RECEIPTS
                 if receipts.get(n, {}).get("recomputed_by") != ARM_ID]
    authorship = {
        "receipt": "receipt_authorship/1", "recomputed_by": ARM_ID,
        "ok": not inherited, "inherited_required_receipts": inherited,
        "required": list(V12_REQUIRED_RECEIPTS),
        "note": ("every required receipt must be recomputed by this arm against the RESTAMPED "
                 "predictions and sidecar; an inherited green receipt describes a different "
                 "arm's identity and does not count")}
    receipts["receipt_authorship"] = authorship

    emitted_sidecar_digest = sidecar_identity(sidecar)
    permitted = (not failed) and (not inherited)

    out.update({
        "arm_id": ARM_ID, "fold_id": fold_id,
        "predictions": preds, "provenance_sidecar": sidecar,
        "provenance_sidecar_digest": emitted_sidecar_digest,
        "receipts": receipts, "inner_receipts": inner_receipts,
        "inner_receipts_note": ("the inherited modelling core's own receipts, retained for "
                                "audit. They describe the legacy synthetic identity shim and "
                                "take NO part in this arm's verdict."),
        "validation_receipts": prediction,
        "required_receipts": list(V12_REQUIRED_RECEIPTS),
        "failed_receipts": failed, "inherited_receipts": inherited,
        "validated": permitted, "scoring_permitted": permitted,
        "snapshot_hash": snap, "config_hash": cfg,
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "legacy_identity_shim": LEGACY_SHIM_ID,
        "declared_defaults_permitted": False,
        "scoring_note": ("scoring_permitted requires every named receipt to pass AND to have "
                         "been recomputed by this arm. This runner computes no accuracy, "
                         "coverage score or profitability figure in any case."),
    })
    return out


def run_player_fold(train, test, fold_id, **kw) -> dict:
    """All four player targets over canonically keyed obligations, defaults forced off."""
    return _run("player", train, test, fold_id, **kw)


def run_team_fold(train, test, fold_id, **kw) -> dict:
    """The team target. `test` needs neither `team_points` nor any `ch_*`."""
    return _run("team", train, test, fold_id, **kw)
