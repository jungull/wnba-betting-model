"""`contract_baseline_suite_v13` — the player order corrected, the player path opened.

WHY THIS ARM EXISTS
-------------------

`contract_baseline_suite_v12` was accepted as the fit-boundary correction it claimed to be: its
real team cold-start path is executable and its player path correctly fails closed before fitting.
What it failed closed *on* is the last thing standing between contract v4 and a real player run:

    `cbs_generator.order_obligations` refuses rows indistinguishable on
    `(player_id, season, forecast_cutoff, game_id)`. The rule is sound — leaving the order to
    however the frame arrived would make every shifted feature depend on input order. The tuple
    is TEAM-BLIND, and `prediction_contract_v4` deliberately carries dual-team obligations: one
    player, one game, one cutoff, two clubs, two forecasts owed. 28 rows, 14 groups, in every
    season 2021-2026. Adding `team_id` resolves all 28.

The supervisor ruled (reply `20260802T232025204Z`): register a new arm and a new ordering
component, make the smallest explicit player-runner fork needed to call it, and preserve the
registered estimator, masks, tuning, calibration and walk-forward logic byte-for-byte except for
the ordering seam and this arm's identity/receipt wrapper. That is exactly what is here and
nothing else.

THE THREE PIECES
----------------

1. **`cbs_obligation_order/2`** — `(player_id, season, forecast_cutoff, game_id, team_id,
   row_uid)`. `team_id` distinguishes the dual-team pair; `row_uid` is the terminal tie-breaker,
   so the order is TOTAL and uniqueness is re-asserted AFTER sorting, not only before. Because
   the sort is stable and the key is an extension of `/1`'s, everything `/1` could already
   distinguish keeps its relative order: the refusal is strictly narrower, never wider.
2. **`cbs_player_runner/13`** — `cbs_v8.run_player_fold`, generated from
   `inspect.getsource` so the copy is exact by construction, with exactly TWO lines changed, both
   of them the ordering call. Every other name is imported from `cbs_v8`, so the estimator, the
   standardizer, the lambda and alpha selection, the masks, the calibration, the dispersion, the
   walk-forward plan and the emission are the same objects and cannot drift. §7 of the v13 suite
   re-derives the diff against the live inherited source and fails on any third differing line.
3. **This wrapper** — v12's fit boundary, rebound to the v13 arm. Every real check v12 performs
   is performed here, by calling v12's own functions rather than by copying them: the real
   manifest stamps, the per-fold frame map, the exact five artifact bytes against disk, every
   frame digest, the canonical key, the forced-off declared defaults, the escape-free feature
   source validation, and the post-restamp recomputation of all eight receipts with an inherited
   receipt failing the run even when it reports `ok`.

WHAT `team_id` IS, AND IS NOT
------------------------------

**An ordering discriminator only.** It enters no grouping, no admission rule, no feature and no
estimator. Player history remains grouped by `(player_id, season)`, so it follows a player across
a trade rather than resetting at it — `cbs_obligation_order.require_history_grouping_unchanged`
asserts that against the registered constant instead of trusting this paragraph.

Two obligations at the same cutoff both receive forecasts, and neither enters the other's
AVAILABILITY-GATED history. That is structural, not incidental: admission is
`availability < cutoff`, and `cbs_v7.require_own_outcome_unavailable` already forbids a row's own
outcome from being available at its own cutoff, so a dual-team sibling — same game, same cutoff —
is never strictly earlier. It covers `n_prior_available_obligations`, `n_prior_appearances`,
`p_plays_prior` and every EWMA and conditional center, and §5 of the v13 suite asserts it on the
REAL collision.

It does **not** cover `n_prior_candidate_games`. `cbs_v8._prior_by_cutoff` is documented as "Prior
rows by CUTOFF" and implemented as a POSITIONAL prefix, so a sibling counts as prior to whichever
of the pair the sort puts second. That count carries no outcome and leaks no result, but it feeds
`player_fallback_level` for `p_active`. Measured over the whole contract: 55 rows where the
positional count exceeds the causal one, and **2 obligations** whose `p_active` fallback band
would differ. The ruling requires the walk-forward logic preserved byte-for-byte and
`_prior_by_cutoff` sits inside `player_history_walk_forward`, not inside `run_player_fold`, so
v13 does not repair it: `measure_equal_cutoff_candidate_count` runs on every player fold and
reports the exact counts in the `obligation_order` receipt. Escalated as **blocker 11**.

WHAT THIS ARM IS NOT
--------------------

**No real fitted player output exists, and none is authorized before supervisory review of this
pushed unit.** The arm is executable on the real player path — §8 of the real-integration suite
runs the 2021 fold end to end and proves zero estimator calls, because 2021's training window is
empty — but no chronological player OOF has been generated. Nothing anywhere in this arm computes
or inspects a score, accuracy, calibration, threshold, edge, return or profitability figure, and
no forecast is compared to any outcome. "Coverage" means OBLIGATION COMPLETENESS throughout.

The registered `primary_metric` is deliberately `NOT_YET_COMPUTED`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

import cbs_obligation_key as obk
import cbs_obligation_order as _order
import cbs_player_runner_v13 as _player
import cbs_provenance_v4 as prov4
import cbs_v8 as _core
import cbs_v10 as _v10
import cbs_v12 as _v12
from cbs_identity_v3 import FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE
from cbs_v7 import (AdapterBoundaryError, REGISTRY_PATH, coverage_receipt,
                    exclusion_receipt, require_outer_fold,
                    recompute_registered_config_hash as _recompute_for)
from cbs_v8 import (FrameBindingError, PLAYER_TARGETS,
                    REQUIRED_PLAYER_FEATURE_SOURCES, REQUIRED_TEAM_FEATURE_SOURCES,
                    SourceProvenanceError, TEAM_TARGET, verify_artifact_bytes)

ARM_ID = "contract_baseline_suite_v13"

#: Unchanged from v12, which was unchanged from v11. This arm corrects an ordering, not a
#: contract: no artifact under `experiments/prediction_contract_v4/` is rebuilt or reread
#: differently.
ROW_UNIVERSE = "prediction_contract_v4"
SNAPSHOT_MANIFEST_SCHEMA = prov4.SNAPSHOT_MANIFEST_SCHEMA
REJECTED_MANIFEST_SCHEMAS = prov4.REJECTED_MANIFEST_SCHEMAS
FRAME_BINDING_SCHEMA = _v10.FRAME_BINDING_SCHEMA
SIDECAR_DIGEST_SCHEMA = _v12.SIDECAR_DIGEST_SCHEMA
TEAM_KEY_ID = _v12.TEAM_KEY_ID

ORDER_ID = _order.ORDER_ID
PLAYER_RUNNER_ID = _player.RUNNER_ID

IDENTITY_BINDING_SCHEMA = "identity_binding/6"
SOURCE_PROVENANCE_SCHEMA = _v12.SOURCE_PROVENANCE_SCHEMA
PROVENANCE_HISTORY_SCHEMA = "provenance_history/3"
PREDICTION_VALIDATION_SCHEMA = "prediction_validation/4"
LEGACY_SHIM_ID = _v12.LEGACY_SHIM_ID
OBLIGATION_ORDER_RECEIPT = "obligation_order/1"

FOLD_FRAME_ROLES = _v12.FOLD_FRAME_ROLES
V13_REQUIRED_RECEIPTS = _v12.V12_REQUIRED_RECEIPTS

#: The registered config digest, recomputed from the registry.
REGISTERED_CONFIG_HASH = \
    "8695cbb60b659a746434287f60417eedd8204c35b4e6d61648b920d9fe194580"

SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v13/synthetic-config").hexdigest()


def recompute_registered_config_hash(registry_path: Path | str = REGISTRY_PATH,
                                     *, experiment_id: str = ARM_ID) -> str:
    """SHA-256 over the registry's frozen_config for **this** arm by default."""
    return _recompute_for(registry_path, experiment_id=experiment_id)


# --------------------------------------------------------------------------
# identity — v12's boundary, called rather than copied
# --------------------------------------------------------------------------

snapshot_identity = _v12.snapshot_identity
require_canonical_keys = _v12.require_canonical_keys
require_fold_frame_map = _v12.require_fold_frame_map
require_real_sources = _v12.require_real_sources
require_team_universe_key = _v12.require_team_universe_key
build_legacy_identity_shim = _v12.build_legacy_identity_shim
sidecar_identity = _v12.sidecar_identity
order_collisions = _v12.order_collisions


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                frames: dict, synthetic: bool,
                                artifact_root: Path | str | None = None,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """v12's accepted boundary, clause for clause, bound to the v13 identity.

    The clauses are v12's own functions, called here. Only the two things that genuinely differ
    between the arms are restated: which registered config digest is expected, and which arm the
    receipt names. Copying the clause bodies to change an arm id is how two gates that were meant
    to be identical stop being identical.
    """
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v13'} digest {expected_cfg}; got {config_hash!r}")

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
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"]),
            "artifact_bytes": bytes_receipt,
            "frame_binding": binding,
            "canonical_keys": keys}


def build_fold_manifest(train, test, universe=None, *, root=prov4.REPO_ROOT,
                        require_attested: bool = True) -> dict:
    """A `/5` manifest over exactly the frames this fold will consume. v12's builder."""
    return _v12.build_fold_manifest(train, test, universe, root=root,
                                    require_attested=require_attested)


def player_history_grouping_in_use() -> tuple:
    """Read the `group_cols` the FORKED runner actually passes, out of its own source.

    Not a constant restated here and not a comment: the AST of
    `cbs_player_runner_v13.run_player_fold` is parsed and every
    `build_walk_forward_plan(..., group_cols=[...])` call's literal is collected. If a future
    edit ever put `team_id` into the grouping — the one change that would silently reset a traded
    player's history without raising anything — this reads it and
    `require_history_grouping_unchanged` refuses the run.
    """
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
    return receipt


def measure_equal_cutoff_candidate_count(train, test) -> dict:
    """Measure where the inherited POSITIONAL prior count disagrees with a causal one.

    The supervisor required proof that equal-cutoff dual-team rows cannot leak into one
    another's lagged history. For every AVAILABILITY-GATED quantity that is true and structural:
    `cbs_v7.build_walk_forward_plan` admits a prior row only when `availability < cutoff`, and
    `require_own_outcome_unavailable` already forbids a row's own outcome from being available at
    its own cutoff, so a dual-team sibling — same game, same cutoff — is never admitted. That
    covers `n_prior_available_obligations`, `n_prior_appearances`, `p_plays_prior` and every EWMA
    and conditional center.

    It is NOT true of `n_prior_candidate_games`. `cbs_v8._prior_by_cutoff` is documented as
    "Prior rows by CUTOFF — a scheduling fact, needing no availability gate" and is implemented
    as a POSITIONAL prefix: every earlier row in sort order counts, whether or not its cutoff is
    strictly earlier. A same-cutoff sibling therefore counts as prior to whichever of the pair
    the sort puts second. That count is not an outcome and leaks no result, but it feeds
    `player_fallback_level` for `p_active`, so it can move a row between the ladder's bands.

    `cbs_v8` and its walk-forward logic are registered and the supervisor's ruling requires them
    preserved byte-for-byte, so v13 does not repair this. It MEASURES it on every player fold and
    reports it in the receipt, so the quantity is pinned and can never grow silently. See
    blocker 11.
    """
    import numpy as np
    from cbs_v7 import PLAYER_SHORT_HISTORY_MAX
    from cbs_v7 import combine_history_frames

    combined = combine_history_frames(train, test)
    need = ("player_id", "season", "forecast_cutoff")
    if any(c not in combined.columns for c in need):
        return {"receipt": "equal_cutoff_candidate_count/1", "ok": True,
                "not_measurable": f"combined frame lacks {[c for c in need if c not in combined]}"}

    d = combined.sort_values(list(_order.ORDER_KEY), kind="mergesort").reset_index(drop=True)
    d["_cut"] = pd.to_datetime(d["forecast_cutoff"], utc=True, errors="coerce")
    positional = d.groupby(["player_id", "season"]).cumcount().to_numpy()
    causal = np.empty(len(d), dtype=int)
    for _, g in d.groupby(["player_id", "season"], sort=False):
        c = g["_cut"].to_numpy()
        causal[g.index.to_numpy()] = np.searchsorted(np.sort(c), c, side="left")

    def band(n):
        return "none" if n <= 0 else ("short" if n <= PLAYER_SHORT_HISTORY_MAX else "long")

    differs = positional != causal
    band_differs = np.array([band(p) != band(c) for p, c in zip(positional, causal)])
    affected = d.loc[band_differs, "row_uid"].astype(str).tolist() \
        if "row_uid" in d.columns else []
    return {
        "receipt": "equal_cutoff_candidate_count/1", "ok": True, "recomputed_by": ARM_ID,
        "quantity": "n_prior_candidate_games",
        "inherited_rule": "cbs_v8._prior_by_cutoff, POSITIONAL prefix within (player_id, season)",
        "causal_rule_compared_against": "obligations with a STRICTLY EARLIER forecast_cutoff",
        "n_rows": int(len(d)),
        "n_rows_where_positional_exceeds_causal": int(differs.sum()),
        "n_rows_whose_p_active_fallback_band_would_differ": int(band_differs.sum()),
        "row_uids_whose_band_would_differ": sorted(affected)[:32],
        "player_short_history_max": int(PLAYER_SHORT_HISTORY_MAX),
        "outcome_leak": False,
        "why_not_an_outcome_leak": (
            "n_prior_candidate_games counts scheduled obligations, not results. No outcome, "
            "appearance or box-score value enters it, and every availability-gated history "
            "quantity excludes the equal-cutoff sibling correctly."),
        "not_repaired_here": (
            "cbs_v8's walk-forward logic is registered and the ruling requires it preserved "
            "byte-for-byte. Measured and reported instead; escalated as blocker 11."),
    }


def require_orderable_obligations(frames: dict) -> dict:
    """The v12 blocker, now a POSITIVE check: the frames must be totally orderable.

    v12 could only measure that the inherited key could not name these obligations and refuse.
    Here the full `/2` key is applied and the result is asserted to be a total order, so the same
    seam that used to stop the run is now what licenses it. A frame that still ties — a genuine
    duplicate `row_uid` — is refused before any estimator is reachable, which §6 asserts with a
    zero-fit counter.
    """
    per_frame, inherited_would = {}, {}
    for role in ("train", "test"):
        f = frames.get(role)
        if f is None or not len(f):
            per_frame[role] = {"n_rows": 0, "vacuous": True}
            continue
        per_frame[role] = _order.assert_total_order(f, where=f"{role} frame")
        refused, why = _order.inherited_would_refuse(f)
        inherited_would[role] = {"refused": refused, "reason": why[:240]}
        per_frame[role]["n_rows_the_inherited_key_could_not_name"] = int(
            f.duplicated(subset=list(_order.INHERITED_KEY), keep=False).sum())
    return {"receipt": "inherited_ordering/2", "ok": True, "recomputed_by": ARM_ID,
            "order_id": ORDER_ID, "supersedes": _order.SUPERSEDES,
            "order_key": list(_order.ORDER_KEY),
            "per_frame": per_frame,
            "inherited_order_would_have_refused": inherited_would}


# --------------------------------------------------------------------------
# receipts
# --------------------------------------------------------------------------

def validate_provenance_sidecar(sidecar: pd.DataFrame, preds: dict, *,
                                fold_id: str, config_hash: str,
                                snapshot_hash: str) -> dict:
    """v12's post-restamp sidecar validator, rebound to the v13 arm.

    The arm substitution is the project's established technique — `cbs_v10` uses it on `cbs_v8`
    and `cbs_v12` on the same — and for the same reason: temporarily reassigning another module's
    global is not reentrant. It is applied to the sidecar AND to the prediction copies together,
    so every cross-frame comparison stays verdict-identical, and it is proved confined to the
    `arm_id` column rather than asserted. The authoritative digest is taken over the untouched
    v13 sidecar.
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
    out["digest_names"] = "the restamped v13 sidecar this run returns, untouched"
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
    """v12's fit boundary with the player delegation swapped for the forked runner."""
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
    # The CLAUSES are v12's and are called, not copied — that is the point. But the receipt has
    # to say which arm recomputed it against THIS run's frames, or the authorship check below
    # would read a genuinely fresh receipt as inherited. Both facts are recorded.
    src_receipt = dict(src_receipt, arm_id=ARM_ID, recomputed_by=ARM_ID,
                       computed_by_clause_set="cbs_v12.require_real_sources")

    require_declared_key = which == "player"
    team_key = (require_team_universe_key(universe)
                if which == "team" and universe is not None else None)

    if which == "player":
        ordering = require_orderable_obligations({"train": train, "test": test})
        ordering["history_grouping"] = require_history_grouping_unchanged()
        ordering["equal_cutoff_candidate_count"] = measure_equal_cutoff_candidate_count(
            train, test)
    else:
        ordering = {"receipt": "inherited_ordering/2", "ok": True, "recomputed_by": ARM_ID,
                    "not_applicable": "cbs_v8.run_team_fold does not order obligations"}

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

    failed = [n for n in V13_REQUIRED_RECEIPTS if not receipts.get(n, {}).get("ok")]
    inherited = [n for n in V13_REQUIRED_RECEIPTS
                 if receipts.get(n, {}).get("recomputed_by") != ARM_ID]
    receipts["receipt_authorship"] = {
        "receipt": "receipt_authorship/1", "recomputed_by": ARM_ID,
        "ok": not inherited, "inherited_required_receipts": inherited,
        "required": list(V13_REQUIRED_RECEIPTS),
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
        "required_receipts": list(V13_REQUIRED_RECEIPTS),
        "failed_receipts": failed, "inherited_receipts": inherited,
        "validated": permitted, "scoring_permitted": permitted,
        "snapshot_hash": snap, "config_hash": cfg,
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "obligation_order_id": ORDER_ID,
        "player_runner_id": PLAYER_RUNNER_ID if which == "player" else None,
        "legacy_identity_shim": LEGACY_SHIM_ID,
        "declared_defaults_permitted": False,
        "scoring_note": ("scoring_permitted requires every named receipt to pass AND to have "
                         "been recomputed by this arm. This runner computes no accuracy, "
                         "coverage score or profitability figure in any case."),
    })
    return out


def run_player_fold(train, test, fold_id, **kw) -> dict:
    """All four player targets, over a TOTALLY ORDERED set of canonical obligations."""
    return _run("player", train, test, fold_id, **kw)


def run_team_fold(train, test, fold_id, **kw) -> dict:
    """The team target, unchanged from v12 except for the arm identity it is stamped with."""
    return _run("team", train, test, fold_id, **kw)
