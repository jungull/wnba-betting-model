"""`contract_baseline_suite_v14` — the prior-obligation count corrected at its definition.

WHY THIS ARM EXISTS
-------------------

v13 opened the real player path and was accepted as a partial correction. It also **measured** a
defect it did not repair: `cbs_v8._prior_by_cutoff` is documented as *"Prior rows by CUTOFF"* and
implemented as a **positional prefix**, so for an equal-cutoff dual-team pair the sibling the sort
puts second counts the first as prior. The supervisor ruled (`20260803T002715462Z`):

    The remaining count defect changes an actual decision for two 2022 obligations, so measuring
    it is not enough. […] Add a new prior-count component that defines `n_prior_candidate_games`
    precisely as the number of candidate obligations in the same `(player_id, season)` whose
    `forecast_cutoff` is strictly earlier than the current cutoff. It is not a count of distinct
    game IDs. Widen the player fork by exactly this one history seam.

WHAT CHANGES
------------

1. **`cbs_player_history/14`** — the count, defined by cutoff. It CALLS
   `cbs_v8.player_history_walk_forward` and replaces exactly two of its seven columns:
   `n_prior_candidate_games` and the flag derived from it. Every availability-gated quantity is
   the inherited one, untouched, and `assert_only_the_count_moved` re-runs the inherited function
   and diffs column by column so the confinement is checked rather than promised.
2. **`cbs_player_runner/14`** — the fork widened from two seams to three, still generated from
   `inspect.getsource` so the copy is exact by construction, still parity-checked at test time
   against the live inherited source.
3. **`cbs_obligation_order/3`** — two v13 accounting claims made true. `/2` validated its INPUT
   while its docstring and test said it validated the ordered result, and its
   `row_set_unchanged` compared row COUNTS under the name of a row-SET proof. `/3` sorts first and
   validates the returned frame, and compares canonical-key sets. `/2` is byte-untouched and
   remains a valid `/2`.

WHAT DOES NOT CHANGE
--------------------

`prediction_contract_v4`, `cbs_generator`, `cbs_v8`, `cbs_v12`, `cbs_v13` and every earlier arm
are byte-untouched, and no module's globals are rebound. The fit boundary is v12's, accepted, and
is CALLED rather than copied — the same discipline v13 used, one level on. The estimator, masks,
tuning, calibration, availability gates, conditional history and grouping rules are all the
inherited ones.

WHAT THIS ARM IS NOT
--------------------

**No real fitted player output exists, and none is authorized before supervisory review of this
pushed unit.** The real 2021 fold traverses the complete boundary and fits nothing, because 2021's
training window is empty; a runtime sentinel asserts it. Nothing here computes or inspects a
score, accuracy, calibration, threshold, edge, return or profitability figure, and no forecast is
compared to any outcome. "Coverage" means OBLIGATION COMPLETENESS throughout.

The registered `primary_metric` is deliberately `NOT_YET_COMPUTED`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

import cbs_obligation_key as obk
import cbs_obligation_order_v3 as _order
import cbs_player_history_v14 as _history
import cbs_player_runner_v14 as _player
import cbs_provenance_v4 as prov4
import cbs_v8 as _core
import cbs_v10 as _v10
import cbs_v12 as _v12
import cbs_v13 as _v13
from cbs_identity_v3 import FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE
from cbs_v7 import (AdapterBoundaryError, REGISTRY_PATH, coverage_receipt,
                    exclusion_receipt, require_outer_fold,
                    recompute_registered_config_hash as _recompute_for)
from cbs_v8 import (FrameBindingError, PLAYER_TARGETS,
                    REQUIRED_PLAYER_FEATURE_SOURCES, REQUIRED_TEAM_FEATURE_SOURCES,
                    SourceProvenanceError, TEAM_TARGET, verify_artifact_bytes)

ARM_ID = "contract_baseline_suite_v14"

ROW_UNIVERSE = "prediction_contract_v4"
SNAPSHOT_MANIFEST_SCHEMA = prov4.SNAPSHOT_MANIFEST_SCHEMA
REJECTED_MANIFEST_SCHEMAS = prov4.REJECTED_MANIFEST_SCHEMAS
FRAME_BINDING_SCHEMA = _v10.FRAME_BINDING_SCHEMA
SIDECAR_DIGEST_SCHEMA = _v12.SIDECAR_DIGEST_SCHEMA
TEAM_KEY_ID = _v12.TEAM_KEY_ID

ORDER_ID = _order.ORDER_ID
PLAYER_RUNNER_ID = _player.RUNNER_ID
HISTORY_ID = _history.HISTORY_ID

IDENTITY_BINDING_SCHEMA = "identity_binding/7"
SOURCE_PROVENANCE_SCHEMA = _v12.SOURCE_PROVENANCE_SCHEMA
PROVENANCE_HISTORY_SCHEMA = "provenance_history/4"
PREDICTION_VALIDATION_SCHEMA = "prediction_validation/5"
LEGACY_SHIM_ID = _v12.LEGACY_SHIM_ID

FOLD_FRAME_ROLES = _v12.FOLD_FRAME_ROLES
V14_REQUIRED_RECEIPTS = _v12.V12_REQUIRED_RECEIPTS

#: The registered config digest, recomputed from the registry.
REGISTERED_CONFIG_HASH = \
    "d91fad4798558e7edd0d62231e2c0c3dd167733719ddb3435d95ad90605ff5aa"

SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v14/synthetic-config").hexdigest()


def recompute_registered_config_hash(registry_path: Path | str = REGISTRY_PATH,
                                     *, experiment_id: str = ARM_ID) -> str:
    """SHA-256 over the registry's frozen_config for **this** arm by default."""
    return _recompute_for(registry_path, experiment_id=experiment_id)


# --------------------------------------------------------------------------
# the fit boundary — v12's, accepted, called rather than copied
# --------------------------------------------------------------------------

snapshot_identity = _v12.snapshot_identity
require_canonical_keys = _v12.require_canonical_keys
require_fold_frame_map = _v12.require_fold_frame_map
require_real_sources = _v12.require_real_sources
require_team_universe_key = _v12.require_team_universe_key
build_legacy_identity_shim = _v12.build_legacy_identity_shim
sidecar_identity = _v12.sidecar_identity
build_fold_manifest = _v12.build_fold_manifest


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                frames: dict, synthetic: bool,
                                artifact_root: Path | str | None = None,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """v12's accepted boundary, clause for clause, bound to the v14 identity."""
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v14'} digest {expected_cfg}; got {config_hash!r}")

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

    real_manifest = None
    if not synthetic:
        real_manifest = prov4.require_real_snapshot_manifest(snapshot_manifest)

    fold_map = require_fold_frame_map(snapshot_manifest, frames)

    derived = snapshot_identity(snapshot_manifest)
    if not isinstance(snapshot_hash, str) or snapshot_hash.lower() != derived:
        raise AdapterBoundaryError(
            f"snapshot_hash must equal the identity DERIVED from the manifest ({derived}); "
            f"got {snapshot_hash!r}")

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

    binding = _v10.bind_frames(snapshot_manifest, frames)
    if not binding["ok"]:
        raise FrameBindingError("; ".join(binding["problems"]))

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
            "obligation_order_id": ORDER_ID,
            "player_history_id": HISTORY_ID,
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"]),
            "artifact_bytes": bytes_receipt,
            "frame_binding": binding,
            "canonical_keys": keys}


# --------------------------------------------------------------------------
# the two corrected seams, receipted
# --------------------------------------------------------------------------

def player_history_grouping_in_use() -> tuple:
    """Read the `group_cols` the v14 FORK actually passes, out of its own source AST."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(_player.run_player_fold))
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
        if name != "build_walk_forward_plan":
            continue
        for kw in node.keywords:
            if kw.arg == "group_cols":
                try:
                    found.add(tuple(ast.literal_eval(kw.value)))
                except (ValueError, SyntaxError):
                    found.add(("<not a literal>",))
    if not found:
        raise AdapterBoundaryError(
            "the forked player runner makes no build_walk_forward_plan call with an explicit "
            "group_cols; the history grouping cannot be verified")
    if len(found) != 1:
        raise AdapterBoundaryError(
            f"the forked player runner groups player history inconsistently: {sorted(found)}")
    return found.pop()


def require_history_grouping_unchanged() -> dict:
    """`team_id` is an ordering discriminator only — checked against the fork's own source."""
    receipt = _order.require_history_grouping_unchanged(player_history_grouping_in_use())
    receipt["read_from"] = f"{PLAYER_RUNNER_ID} source AST"
    receipt["order_id"] = ORDER_ID
    return receipt


def require_orderable_obligations(frames: dict) -> dict:
    """The frames must be totally orderable under `/3`, checked on the ORDERED result."""
    per_frame, inherited_would = {}, {}
    for role in ("train", "test"):
        f = frames.get(role)
        if f is None or not len(f):
            per_frame[role] = {"n_rows": 0, "vacuous": True}
            continue
        ordered = _order.order_obligations_v3(f, where=f"{role} frame")
        per_frame[role] = _order.assert_total_order(ordered, where=f"{role} frame (ordered)")
        per_frame[role]["validated_on"] = "the ORDERED frame"
        refused, why = _order.inherited_would_refuse(f)
        inherited_would[role] = {"refused": refused, "reason": why[:240]}
        per_frame[role]["n_rows_the_inherited_key_could_not_name"] = int(
            f.duplicated(subset=list(_order.INHERITED_KEY), keep=False).sum())
        per_frame[role]["order_receipt"] = _order.order_receipt_v3(f, ordered, role=role)
    return {"receipt": "inherited_ordering/3", "ok": True, "recomputed_by": ARM_ID,
            "order_id": ORDER_ID, "supersedes": _order.SUPERSEDES,
            "order_key": list(_order.ORDER_KEY),
            "per_frame": per_frame,
            "inherited_order_would_have_refused": inherited_would}


def require_corrected_prior_count(train, test) -> dict:
    """The prior-obligation count must be by CUTOFF, and the seam must be confined.

    Both properties are asserted on the frame the run will actually consume — the combined
    history frame, built exactly as the runner builds it — rather than on a fixture. v13 measured
    this defect and reported it; here it is corrected, and the correction is proved twice: the
    seam touched only the two columns it was allowed to touch, and every equal-cutoff group's
    members received one shared count.
    """
    from cbs_v7 import build_walk_forward_plan, combine_history_frames
    from cbs_v5 import PLAYER_SORT_KEYS

    combined = combine_history_frames(train, test)
    if "appeared" not in combined.columns:
        combined = combined.assign(appeared=pd.NA)
    plan = build_walk_forward_plan(combined, group_cols=list(_history.GROUP_COLS),
                                   sort_cols=list(PLAYER_SORT_KEYS))
    seam = _history.assert_only_the_count_moved(combined, plan)
    agree = _history.equal_cutoff_agreement(combined, plan)
    problems = list(agree.get("problems", []))
    return {"receipt": "prior_obligation_count/1", "ok": not problems, "recomputed_by": ARM_ID,
            "problems": problems,
            "history_id": HISTORY_ID,
            "supersedes": _history.SUPERSEDES,
            "definition": _history.COUNT_DEFINITION,
            "counts_obligations_not_distinct_game_ids": True,
            "availability_gated": False,
            "seam": seam, "equal_cutoff_agreement": agree}


# --------------------------------------------------------------------------
# receipts
# --------------------------------------------------------------------------

def validate_provenance_sidecar(sidecar: pd.DataFrame, preds: dict, *,
                                fold_id: str, config_hash: str,
                                snapshot_hash: str) -> dict:
    """v12's post-restamp sidecar validator, rebound to the v14 arm.

    The arm substitution is the project's established technique and is applied to the sidecar AND
    the prediction copies together, so every cross-frame comparison stays verdict-identical. The
    authoritative digest is taken over the untouched v14 sidecar.
    """
    problems: list[str] = []
    if "arm_id" not in sidecar.columns:
        return {"receipt": PROVENANCE_HISTORY_SCHEMA, "ok": False, "recomputed_by": ARM_ID,
                "arm_id": ARM_ID, "problems": ["sidecar missing arm_id"]}
    if (sidecar["arm_id"] != ARM_ID).any():
        problems.append(f"sidecar arm_id is not uniformly {ARM_ID!r}")
    for tgt, p in preds.items():
        if "arm_id" not in p.columns:
            problems.append(f"{tgt}: emitted predictions carry no arm_id")
        elif (p["arm_id"] != ARM_ID).any():
            problems.append(f"{tgt}: emitted predictions are not uniformly {ARM_ID!r}")

    probe_sc = sidecar.copy()
    probe_sc["arm_id"] = _v12.ARM_ID
    probe_pr = {}
    for tgt, p in preds.items():
        q = p.copy()
        q["arm_id"] = _v12.ARM_ID
        probe_pr[tgt] = q
    drifted = [c for c in sidecar.columns
               if c != "arm_id"
               and not sidecar[c].astype(str).equals(probe_sc[c].astype(str))]
    if drifted:
        problems.append(f"the v12 validation probe differs from the emitted sidecar in columns "
                        f"other than arm_id: {drifted}")

    inner = _v12.validate_provenance_sidecar(
        probe_sc, probe_pr, fold_id=fold_id, config_hash=config_hash,
        snapshot_hash=snapshot_hash)

    out = dict(inner)
    out["problems"] = problems + list(inner.get("problems", []))
    out["receipt"] = PROVENANCE_HISTORY_SCHEMA
    out["arm_id"] = ARM_ID
    out["recomputed_by"] = ARM_ID
    out["inherited_clause_set"] = _v12.PROVENANCE_HISTORY_SCHEMA
    out["digest"] = sidecar_identity(sidecar)
    out["digest_schema"] = SIDECAR_DIGEST_SCHEMA
    out["digest_names"] = "the restamped v14 sidecar this run returns, untouched"
    out["probe_substituted_columns"] = sorted(
        {"arm_id", *inner.get("probe_substituted_columns", [])})
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
    """v12's fit boundary with the player delegation swapped for the three-seam fork."""
    from contract_validator_v4_strict import validate_arm_output_v4

    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    cfg, snap = identity["config_hash"], identity["snapshot_hash"]

    fold = dict(require_outer_fold(train, test, fold_id))
    fold["recomputed_by"] = ARM_ID
    fold.setdefault("receipt", "fold_boundary/1")
    fold["ok"] = bool(fold.get("ok", True))

    sources = (REQUIRED_PLAYER_FEATURE_SOURCES if which == "player"
               else REQUIRED_TEAM_FEATURE_SOURCES)
    src_receipt, _feature_asof = require_real_sources(train, test, sources)
    if not src_receipt["ok"]:
        raise SourceProvenanceError("; ".join(src_receipt["problems"]))
    src_receipt = dict(src_receipt, arm_id=ARM_ID, recomputed_by=ARM_ID,
                       computed_by_clause_set="cbs_v12.require_real_sources")

    require_declared_key = which == "player"
    team_key = (require_team_universe_key(universe)
                if which == "team" and universe is not None else None)

    if which == "player":
        ordering = require_orderable_obligations({"train": train, "test": test})
        ordering["history_grouping"] = require_history_grouping_unchanged()
        prior_count = require_corrected_prior_count(train, test)
        if not prior_count["ok"]:
            raise AdapterBoundaryError("; ".join(prior_count["problems"]))
        ordering["prior_obligation_count"] = prior_count
    else:
        ordering = {"receipt": "inherited_ordering/3", "ok": True, "recomputed_by": ARM_ID,
                    "not_applicable": "cbs_v8.run_team_fold neither orders obligations nor "
                                      "builds a player history frame"}

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
    fn = _player.run_player_fold if which == "player" else _core.run_team_fold
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
    receipts["obligation_order"] = ordering
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

    failed = [n for n in V14_REQUIRED_RECEIPTS if not receipts.get(n, {}).get("ok")]
    inherited = [n for n in V14_REQUIRED_RECEIPTS
                 if receipts.get(n, {}).get("recomputed_by") != ARM_ID]
    receipts["receipt_authorship"] = {
        "receipt": "receipt_authorship/1", "recomputed_by": ARM_ID,
        "ok": not inherited, "inherited_required_receipts": inherited,
        "required": list(V14_REQUIRED_RECEIPTS),
        "note": ("every required receipt must be recomputed by this arm against the RESTAMPED "
                 "predictions and sidecar; an inherited green receipt describes a different "
                 "arm's identity and does not count")}

    permitted = (not failed) and (not inherited)
    out.update({
        "arm_id": ARM_ID, "fold_id": fold_id,
        "predictions": preds, "provenance_sidecar": sidecar,
        "provenance_sidecar_digest": sidecar_identity(sidecar),
        "receipts": receipts, "inner_receipts": inner_receipts,
        "inner_receipts_note": ("the inherited modelling core's own receipts, retained for "
                                "audit. They describe the legacy synthetic identity shim and "
                                "take NO part in this arm's verdict."),
        "validation_receipts": prediction,
        "required_receipts": list(V14_REQUIRED_RECEIPTS),
        "failed_receipts": failed, "inherited_receipts": inherited,
        "validated": permitted, "scoring_permitted": permitted,
        "snapshot_hash": snap, "config_hash": cfg,
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "obligation_order_id": ORDER_ID,
        "player_history_id": HISTORY_ID if which == "player" else None,
        "player_runner_id": PLAYER_RUNNER_ID if which == "player" else None,
        "legacy_identity_shim": LEGACY_SHIM_ID,
        "declared_defaults_permitted": False,
        "scoring_note": ("scoring_permitted requires every named receipt to pass AND to have "
                         "been recomputed by this arm. This runner computes no accuracy, "
                         "coverage score or profitability figure in any case."),
    })
    return out


def run_player_fold(train, test, fold_id, **kw) -> dict:
    """All four player targets, totally ordered, with the prior count defined by cutoff."""
    return _run("player", train, test, fold_id, **kw)


def run_team_fold(train, test, fold_id, **kw) -> dict:
    """The team target, unchanged except for the arm identity it is stamped with."""
    return _run("team", train, test, fold_id, **kw)
