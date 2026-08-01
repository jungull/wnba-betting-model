#!/usr/bin/env python3
"""cbs_v8.py — the runner for `contract_baseline_suite_v8`.

v7 closed the outer-fold and as-of boundaries and its 235 synthetic assertions
pass. **v7 is left byte-untouched as the historical record**; every unchanged
primitive is imported from it rather than copied, so the two modules cannot drift
apart and a reader can diff exactly what v8 changed.

v7's remaining defects were all in the same family: it proved things about the
frame it *predicted* and took the frame it *fitted on* — and the artifacts both
came from — on trust.

WHAT v8 CLOSES
--------------
1. **Training feature provenance was never resolved.** `resolve_feature_asof_strict`
   ran on `test` only (`cbs_v7.py:1212`, `:1467`). Training Stage-A values and team
   channels were fitted without ever proving their source timestamps preceded each
   *training* row's cutoff — so a model could be fitted on features assembled after
   the fact and still emit a clean receipt. v8 resolves, validates and receipts
   **every** frame it reads: training, prediction, and the combined history.
2. **A team "current obligation" still required its own postgame outcome.**
   `require_team_predict_inputs` called `_require_team_common`, which demands all
   four `ch_*` components be present, non-null and finite — and those are
   decompositions of the target game's own final box score. v7 removed the
   `team_points` requirement and left the four columns that add up to it. v8
   separates **current obligations** (identity and schedule only) from
   **completed, availability-gated channel history**, and a current row now needs
   neither `team_points` nor any `ch_*`.
3. **The snapshot manifest was bound to nothing.** `snapshot_identity` hashed
   whatever mapping the caller passed. Nothing checked that those digests matched
   real artifact bytes, and nothing tied the manifest to the `train` / `test` /
   `universe` frames actually consumed — so the same manifest could be reused
   across mutated frames. v8 verifies artifact bytes on disk and binds canonical
   per-frame digests, and a mutated frame fails **before any fitting occurs**.

**Synthetic only, and structurally so.** No frame arrives from a path. The only
files this module opens are `experiments/registry.jsonl`, for config identity, and
— when an `artifact_root` is supplied — the snapshot artifacts themselves, whose
bytes are read solely to verify their digests. Neither is ever a model input.
Running this module produces no artifact, no accuracy figure and no coverage score.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cbs_builders import QUANTILE_Z
from cbs_generator import (ALPHA_GRID, DECLARED, SplitContext, Standardizer,
                           logistic_fit, logistic_predict, order_obligations,
                           player_split, prefix_mean, select_alpha_bound, team_split)
from cbs_v5 import (MissingRequiredInput, P_ACTIVE_FEATURES, REQUIRED_CHANNELS,
                    REQUIRED_SIDES, SIDE_COL, TEAM_HISTORY_GROUP, TEAM_MIN_PRIOR,
                    TEAM_SORT_KEYS, PLAYER_SORT_KEYS, apply_side_maps, dispersion,
                    fit_side_maps, residuals)
# --- everything v7 got right, imported rather than copied ------------------
from cbs_v7 import (AdapterBoundaryError, AvailabilityViolation,
                    DECLARED_CONSTANT_SEASONS, FittedState, MAX_FALLBACK_LEVEL,
                    MIN_RESID_PLAYER, MIN_RESID_TEAM,
                    OUTCOME_AVAILABILITY_POLICY_ID,
                    OUTCOME_AVAILABILITY_POLICY_LAG_HOURS, OUTCOME_OBSERVED_AT_COL,
                    OuterFoldViolation, PLAYER_SHORT_HISTORY_MAX,
                    PROVENANCE_SIDECAR_SCHEMA, ProvenanceError, REGISTRY_PATH,
                    SIDECAR_COLS, WalkForwardPlan, build_provenance_rows,
                    build_walk_forward_plan, canonical_digest, combine_history_frames,
                    conditional_center, coverage_receipt, exclusion_receipt,
                    player_fallback_level, recompute_registered_config_hash,
                    require_outer_fold, require_own_outcome_unavailable,
                    resolve_outcome_availability, sidecar_digest, team_fallback_level,
                    walk_forward_counts, walk_forward_ewma)
from contract_validator_v3_strict import validate_arm_output_v3

ARM_ID = "contract_baseline_suite_v8"

PLAYER_TARGETS = ("p_active", "e_minutes_given_active", "attempts_usage",
                  "player_scoring_distribution")
TEAM_TARGET = "team_game_distribution"

SNAPSHOT_MANIFEST_SCHEMA = "cbs_snapshot_manifest/2"
SOURCE_PROVENANCE_SCHEMA = "cbs_source_provenance/1"
FRAME_BINDING_SCHEMA = "cbs_frame_binding/1"

#: The registered config digest, recomputed from the registry by
#: `recompute_registered_config_hash(experiment_id=ARM_ID)`.
REGISTERED_CONFIG_HASH = \
    "663058521c36fd5afc4baaab8fc0a29b6121bf5dc7685df3dc1e8afbc67e43e5"

SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v8/synthetic-config").hexdigest()

#: Stage-A source timestamp columns a REAL adapter must supply, on EVERY frame
#: it hands over — training included.
REQUIRED_PLAYER_FEATURE_SOURCES = ("src_asof_gamelog", "src_asof_roster",
                                   "src_asof_schedule")
REQUIRED_TEAM_FEATURE_SOURCES = ("src_asof_team_gamelog", "src_asof_schedule")

#: Identity and schedule facts a CURRENT team obligation must carry. Note what
#: is absent: `team_points` and every `ch_*`. Those are the target game's own
#: final box score, and a forecast that requires them is not a forecast.
TEAM_CURRENT_OBLIGATION_COLS = ("row_uid", "team_id", "game_id", "season",
                                "game_date", "forecast_cutoff", SIDE_COL)


class FrameBindingError(RuntimeError):
    """A consumed frame does not match the identity the manifest declared."""


class SourceProvenanceError(MissingRequiredInput):
    """A frame's feature-source timestamps are absent, unparseable or too late."""


# --------------------------------------------------------------------------
# 1. source provenance on EVERY frame  (blocker 1)
# --------------------------------------------------------------------------

def resolve_sources_receipted(frame: pd.DataFrame, source_cols, *, role: str,
                              cutoff_col: str = "forecast_cutoff"
                              ) -> tuple[pd.Series, dict]:
    """Derive `feature_asof` for one frame AND return a receipt for it.

    v7 called its resolver on the prediction frame only. That is half a
    guarantee: the fitted coefficients, the selected alphas, the calibration maps
    and the residual pool all come from the TRAINING frame, so training features
    assembled after their own cutoffs would corrupt every one of those and leave
    no trace. The role is recorded so a reader can see which frames were actually
    checked rather than inferring it.

    Raises `SourceProvenanceError` on absence, nulls, unparseable values, or any
    row whose source was read at or after its own cutoff (equality is a
    violation, matching `asof_invariant`).
    """
    missing = [c for c in source_cols if c not in frame.columns]
    if missing:
        raise SourceProvenanceError(
            f"{role} frame: cannot derive feature_asof, source timestamp columns "
            f"absent: {missing}")
    if cutoff_col not in frame.columns:
        raise SourceProvenanceError(f"{role} frame: missing {cutoff_col!r}")

    ts = frame[list(source_cols)].apply(pd.to_datetime, utc=True, errors="coerce")
    null_by_col = {c: int(ts[c].isna().sum()) for c in ts.columns if ts[c].isna().any()}
    if null_by_col:
        raise SourceProvenanceError(
            f"{role} frame: missing or unparseable source timestamps; provenance "
            f"ambiguous: {null_by_col}")

    cutoff = pd.to_datetime(frame[cutoff_col], utc=True, errors="coerce")
    if cutoff.isna().any():
        raise SourceProvenanceError(
            f"{role} frame: unparseable {cutoff_col} on "
            f"{int(cutoff.isna().sum())} rows")

    asof = ts.max(axis=1)
    at_cutoff = int((asof == cutoff).sum())
    after_cutoff = int((asof > cutoff).sum())
    if at_cutoff or after_cutoff:
        raise SourceProvenanceError(
            f"{role} frame: {at_cutoff} rows read a feature source EXACTLY AT and "
            f"{after_cutoff} rows AFTER their own forecast cutoff; those features "
            f"were not available when the forecast was due")

    lead = (cutoff - asof)
    receipt = {
        "role": role, "n_rows": int(len(frame)),
        "sources": list(source_cols),
        "n_at_cutoff": at_cutoff, "n_after_cutoff": after_cutoff,
        "min_lead_seconds": float(lead.min().total_seconds()) if len(frame) else None,
        "max_lead_seconds": float(lead.max().total_seconds()) if len(frame) else None,
        "asof_min": asof.min().isoformat() if len(frame) else None,
        "asof_max": asof.max().isoformat() if len(frame) else None,
    }
    formatted = asof.dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(
        r"(\+0000)$", "+00:00", regex=True)
    return formatted, receipt


def resolve_fold_sources(train: pd.DataFrame, test: pd.DataFrame, source_cols, *,
                         synthetic: bool) -> tuple[pd.Series, dict]:
    """Resolve and receipt the sources for BOTH frames of a fold.

    The three-way branch matters. A frame that carries *some* of the registered
    source columns is rejected rather than quietly downgraded to a declared
    `feature_asof`: partial provenance is ambiguous provenance, and a frame that
    lost one source column would otherwise slip through looking fully derived.
    This mirrors the rule `resolve_outcome_availability` already applies to a
    half-populated observed column — supply them everywhere or nowhere.
    """
    present = [c for c in source_cols if c in test.columns]
    complete = len(present) == len(source_cols)

    if not synthetic or complete:
        feature_asof, test_receipt = resolve_sources_receipted(
            test, source_cols, role="test")
        per_frame = {"test": test_receipt}
        if len(train):
            _, per_frame["train"] = resolve_sources_receipted(
                train, source_cols, role="train")
        return feature_asof, per_frame

    if present:
        raise SourceProvenanceError(
            f"test frame carries only {len(present)} of {len(source_cols)} registered "
            f"feature-source columns ({sorted(present)}); partial source provenance is "
            f"ambiguous and may not fall back to a declared feature_asof")

    if "feature_asof" in test.columns:
        return test["feature_asof"], {}
    raise SourceProvenanceError("no feature source timestamps and no feature_asof")


def source_provenance_receipt(per_frame: dict, *, synthetic: bool) -> dict:
    """One receipt naming every frame whose sources were validated.

    `frames_validated` is the point of this receipt. A reader must be able to see
    that `train` is in the list, because v7's failure was precisely that it was
    not — and nothing in v7's output revealed the omission.
    """
    roles = sorted(per_frame)
    problems = []
    for required in ("train", "test"):
        if required not in per_frame and not synthetic:
            problems.append(f"the {required!r} frame's feature sources were never "
                            f"validated")
    return {
        "receipt": SOURCE_PROVENANCE_SCHEMA, "ok": not problems,
        "problems": problems, "frames_validated": roles,
        "synthetic": bool(synthetic), "per_frame": per_frame,
    }


# --------------------------------------------------------------------------
# 2. artifact-byte and frame identity binding  (blocker 3)
# --------------------------------------------------------------------------

def frame_digest(frame: pd.DataFrame) -> str:
    """A canonical, order-independent digest of a frame's CONTENT.

    Columns are sorted by name and rows by `row_uid`, so neither a reordered
    column list nor a shuffled frame is a different artifact — but any changed
    *value* is. Without this, "the manifest binds the frames" would be satisfiable
    by a frame that merely had the right shape.
    """
    if "row_uid" not in frame.columns:
        raise FrameBindingError("cannot digest a frame without row_uid")
    cols = sorted(frame.columns)
    d = frame[cols].sort_values("row_uid", kind="mergesort")
    payload = []
    for rec in d.astype(object).to_numpy().tolist():
        payload.append([("" if (v is None or (isinstance(v, float) and pd.isna(v)))
                         else str(v)) for v in rec])
    return canonical_digest({"columns": cols, "n_rows": int(len(d)), "rows": payload})


def verify_artifact_bytes(manifest: dict, artifact_root: Path | str) -> dict:
    """Re-hash the artifacts on disk and compare to what the manifest declared.

    A manifest is only evidence if something checks it against the world. v7
    hashed the caller's mapping and never opened a file, so a manifest could
    name artifacts that had since changed — or that never existed.
    """
    root = Path(artifact_root)
    artifacts = manifest.get("artifacts") or {}
    checked, mismatched, absent = [], [], []
    for rel, declared in sorted(artifacts.items()):
        want = declared["sha256"] if isinstance(declared, dict) else declared
        p = root / rel
        if not p.exists():
            absent.append(rel)
            continue
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        (checked if h.hexdigest() == str(want).lower() else mismatched).append(rel)
    problems = []
    if absent:
        problems.append(f"{len(absent)} declared artifacts absent on disk: {absent[:3]}")
    if mismatched:
        problems.append(f"{len(mismatched)} declared artifacts do not match their "
                        f"bytes on disk: {mismatched[:3]}")
    return {"ok": not problems, "problems": problems, "artifact_root": str(root),
            "n_verified": len(checked), "n_absent": len(absent),
            "n_mismatched": len(mismatched), "verified": checked}


def snapshot_identity(manifest: dict) -> str:
    """Derive the snapshot identity from the manifest, which now names FRAMES too."""
    if not isinstance(manifest, dict):
        raise AdapterBoundaryError("snapshot manifest must be a mapping")
    if manifest.get("schema") != SNAPSHOT_MANIFEST_SCHEMA:
        raise AdapterBoundaryError(
            f"snapshot manifest schema must be {SNAPSHOT_MANIFEST_SCHEMA!r}; "
            f"got {manifest.get('schema')!r}")
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
    """Prove the manifest describes THESE frames, before anything is fitted.

    Called at the top of each runner, ahead of every split, selection and fit, so
    a mutated frame cannot get as far as influencing a coefficient. v7's
    `snapshot_identity` was a hash of the caller's own words about the data; this
    is a hash of the data.
    """
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
            "per_frame": per_frame}


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                frames: dict, synthetic: bool,
                                artifact_root: Path | str | None = None,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """Config, snapshot, artifact bytes and frame identity — all four, or raise."""
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v8'} digest {expected_cfg}; "
            f"got {config_hash!r}")

    recomputed = None
    if not synthetic:
        recomputed = recompute_registered_config_hash(registry_path,
                                                      experiment_id=ARM_ID)
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

    return {"receipt": "identity_binding/2", "ok": True, "synthetic": bool(synthetic),
            "config_hash": expected_cfg,
            "config_hash_recomputed_from_registry": recomputed,
            "snapshot_hash": derived,
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"]),
            "artifact_bytes": bytes_receipt,
            "frame_binding": binding}


# --------------------------------------------------------------------------
# 3. team obligations vs completed channel history  (blocker 2)
# --------------------------------------------------------------------------

def _require_team_identity(frame: pd.DataFrame, role: str) -> None:
    """Identity and schedule only — the facts known before a game is played."""
    for k in TEAM_CURRENT_OBLIGATION_COLS:
        if k not in frame.columns:
            raise MissingRequiredInput(f"team {role} frame missing {k!r}")
        if frame[k].isna().any():
            raise MissingRequiredInput(
                f"team {role} frame has null {k!r} on "
                f"{int(frame[k].isna().sum())} rows")
    if pd.to_numeric(frame["season"], errors="coerce").isna().any():
        raise MissingRequiredInput(f"team {role} frame has non-numeric season")
    if pd.to_datetime(frame["game_date"], errors="coerce").isna().any():
        raise MissingRequiredInput(f"team {role} frame has unparseable game_date")
    if pd.to_datetime(frame["forecast_cutoff"], utc=True, errors="coerce").isna().any():
        raise MissingRequiredInput(f"team {role} frame has unparseable forecast_cutoff")
    if frame["row_uid"].duplicated().any():
        raise MissingRequiredInput(f"team {role} frame has duplicate row_uid")
    bad = set(pd.unique(frame[SIDE_COL])) - set(REQUIRED_SIDES)
    if bad:
        raise MissingRequiredInput(f"unexpected {SIDE_COL} values: {sorted(bad)}")
    if frame.duplicated(subset=["team_id", "game_id"]).any():
        raise MissingRequiredInput("duplicate (team_id, game_id) team rows")
    for gid, sides in frame.groupby("game_id")[SIDE_COL].agg(list).items():
        if sorted(sides) != sorted(REQUIRED_SIDES):
            raise MissingRequiredInput(
                f"game {gid!r} is not exactly one home and one away row: {sides}")


def require_team_current_obligations(frame: pd.DataFrame) -> None:
    """A current obligation needs identity and a schedule. Nothing else.

    v7 routed this through the same checker as training, which required all four
    `ch_*` columns present, non-null and finite. Those four are a decomposition of
    the target game's own final score — `ch_ft + ch_3pt + ch_paint + ch_np2`
    reconstructs it — so v7 could not predict a game without being handed the
    answer. Removing `team_points` while keeping its four addends closed nothing.
    """
    _require_team_identity(frame, "current-obligation")
    present = [f"ch_{c}" for c in REQUIRED_CHANNELS if f"ch_{c}" in frame.columns]
    if "team_points" in frame.columns or present:
        # Not an error — a backfilled frame legitimately carries them — but the
        # runner must never REQUIRE them, and must never read them for the row's
        # own prediction. The history engine's availability gate enforces that.
        pass


def require_team_history_inputs(frame: pd.DataFrame) -> None:
    """Completed games that may enter history: outcomes required and finite."""
    _require_team_identity(frame, "history")
    missing = [c for c in REQUIRED_CHANNELS if f"ch_{c}" not in frame.columns]
    if missing:
        raise MissingRequiredInput(
            f"completed history rows must carry every channel; absent: {missing}")
    for c in REQUIRED_CHANNELS:
        col = pd.to_numeric(frame[f"ch_{c}"], errors="coerce")
        if col.isna().any() or not np.isfinite(col).all():
            raise MissingRequiredInput(f"channel ch_{c} has null/non-finite values")
    if "team_points" not in frame.columns:
        raise MissingRequiredInput("team history frame missing team_points")
    y = pd.to_numeric(frame["team_points"], errors="coerce")
    if y.isna().any() or not np.isfinite(y).all():
        raise MissingRequiredInput(
            "training rows have a null or non-finite team_points outcome")


def team_history_usable(frame: pd.DataFrame) -> pd.Series:
    """Which rows carry a COMPLETE channel observation fit to be history.

    A row with a missing channel is not a small observation, it is an absent one.
    It must be excluded from the EWMA *and* from `prior_games`, or `MIN_PRIOR`
    would count games that never reached the average it is supposed to qualify.
    """
    ok = pd.Series(True, index=frame.index)
    for c in REQUIRED_CHANNELS:
        col = (pd.to_numeric(frame[f"ch_{c}"], errors="coerce")
               if f"ch_{c}" in frame.columns else pd.Series(np.nan, index=frame.index))
        ok &= np.isfinite(col)
    return ok


def player_history_usable(frame: pd.DataFrame) -> pd.Series:
    """A prior obligation counts only if its APPEARANCE outcome is actually there."""
    if "appeared" not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame["appeared"].notna()


def player_history_walk_forward(frame: pd.DataFrame, plan: WalkForwardPlan
                                ) -> pd.DataFrame:
    """v7's accounting, with the denominator restricted to rows that HAVE an outcome.

    v7 counted every admitted prior row in `n_prior_available_obligations`, even
    one whose `appeared` was absent because it was a future obligation carried in
    for its schedule. That row can never enter the numerator, so it biased
    `p_plays_prior` downward — a silent, one-sided error.
    """
    usable = player_history_usable(frame)
    appeared = (frame["appeared"].astype(float).fillna(0.0).astype(bool)
                if "appeared" in frame.columns else pd.Series(False, index=frame.index))

    out = pd.DataFrame(index=plan.order)
    out["n_prior_available_obligations"] = walk_forward_counts(
        plan, mask=usable).astype(int)
    out["n_prior_appearances"] = walk_forward_counts(
        plan, mask=(usable & appeared)).astype(int)
    out["n_prior_candidate_games"] = np.asarray(
        [len(p) for p in _prior_by_cutoff(plan)], dtype=int)
    out["has_prior_obligation"] = out["n_prior_candidate_games"] > 0
    out["has_prior_appearance"] = out["n_prior_appearances"] > 0
    out["has_prior_available_obligation"] = out["n_prior_available_obligations"] > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        out["p_plays_prior"] = np.where(
            out["n_prior_available_obligations"] > 0,
            out["n_prior_appearances"]
            / out["n_prior_available_obligations"].replace(0, np.nan), np.nan)
    return out.reindex(frame.index)


def _prior_by_cutoff(plan: WalkForwardPlan) -> list[np.ndarray]:
    """Prior rows by CUTOFF — a scheduling fact, needing no availability gate."""
    out: list[np.ndarray] = []
    seen: dict = {}
    for i, g in enumerate(plan.group_key):
        members = seen.setdefault(g, [])
        out.append(np.asarray(members, dtype=int))
        members.append(i)
    return out


def stage_a_features_v8(frame: pd.DataFrame, hist: pd.DataFrame, base_rate: float,
                        *, allow_declared_defaults: bool) -> pd.DataFrame:
    """The 14 canonical features. On the real path, every one must be supplied."""
    derived = {"p_plays_prior", "player_gp_season"}
    supplied = {c for c in P_ACTIVE_FEATURES if c in frame.columns}
    missing = [c for c in P_ACTIVE_FEATURES if c not in supplied | derived]
    if missing and not allow_declared_defaults:
        raise MissingRequiredInput(
            f"Stage-A features absent and declared defaults are not permitted on "
            f"this path: {missing}")

    X = pd.DataFrame(index=frame.index)
    for c in P_ACTIVE_FEATURES:
        if c == "p_plays_prior":
            X[c] = hist["p_plays_prior"].where(
                hist["has_prior_available_obligation"], base_rate)
        elif c == "player_gp_season":
            X[c] = hist["n_prior_appearances"].astype(float)
        elif c in frame.columns:
            X[c] = pd.to_numeric(frame[c], errors="coerce").astype(float)
        else:
            X[c] = 45.0 if c == "days_since_last_appearance" else 0.0
    X = X[P_ACTIVE_FEATURES].astype(float)
    if not allow_declared_defaults and not np.isfinite(X.to_numpy()).all():
        raise MissingRequiredInput(
            "non-finite Stage-A feature values on the real path; a null feature "
            "may not become a silent zero")
    return X.fillna(0.0)


# --------------------------------------------------------------------------
# 4. emission
# --------------------------------------------------------------------------

def _emit(rows: pd.DataFrame, target: str, point: pd.Series, sd: pd.Series | None,
          offsets: np.ndarray | None, *, fold_id: str, config_hash: str,
          snapshot_hash: str, model_hash: str, feature_asof: pd.Series,
          fallback_level: pd.Series, component_id: pd.Series, is_cold: pd.Series,
          n_prior: pd.Series, exclusion: pd.Series, low, high,
          want_q: bool) -> pd.DataFrame:
    from cbs_builders import emit_quantiles
    lvl = pd.Series(fallback_level, index=rows.index).astype(int)
    out = pd.DataFrame({
        "row_uid": rows["row_uid"].to_numpy(),
        "target_key": target, "arm_id": ARM_ID, "fold_id": fold_id,
        "forecast_cutoff": rows["forecast_cutoff"].to_numpy(),
        "pred_point": np.asarray(point, dtype=float),
        "pred_sd": (np.asarray(sd, dtype=float) if sd is not None
                    else np.full(len(rows), np.nan)),
        "is_fallback": (lvl > 0).to_numpy(),
        "fallback_level": lvl.to_numpy(),
        "component_id": pd.Series(component_id, index=rows.index).to_numpy(),
        "is_cold_start": np.asarray(is_cold, dtype=bool),
        "n_prior_games": np.asarray(n_prior, dtype=int),
        "feature_asof": pd.Series(feature_asof, index=rows.index).to_numpy(),
        "model_hash": model_hash, "config_hash": config_hash,
        "data_snapshot_hash": snapshot_hash,
        "exclusion_reason": pd.Series(exclusion, index=rows.index).to_numpy(),
    })
    for c in ("pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"):
        out[c] = np.nan
    if low is not None:
        out["pred_point"] = out["pred_point"].clip(lower=low)
    if high is not None:
        out["pred_point"] = out["pred_point"].clip(upper=high)
    if want_q and offsets is not None and np.all(np.isfinite(offsets)):
        q = emit_quantiles(out["pred_point"].to_numpy(dtype=float), offsets,
                           low=low, high=high)
        for i, c in enumerate(("pred_q05", "pred_q25", "pred_q50",
                               "pred_q75", "pred_q95")):
            out[c] = q[:, i]
    excl = out.exclusion_reason.notna()
    if excl.any():
        out.loc[excl, ["pred_point", "pred_sd", "pred_q05", "pred_q25",
                       "pred_q50", "pred_q75", "pred_q95"]] = np.nan
    return out


def _provenance_rows(pred, **kw) -> pd.DataFrame:
    """v7's provenance rows, stamped with the v8 arm id.

    v7's builder hardcodes its own `ARM_ID`, and v7 is immutable, so the arm is
    restamped here. It is done by rewriting the column rather than by temporarily
    reassigning `cbs_v7.ARM_ID`: mutating another module's global to borrow its
    function is not reentrant, and a failure between the assignment and the
    restore would leave v7 permanently mislabelled.
    """
    rows = build_provenance_rows(pred, **kw)
    rows["arm_id"] = ARM_ID
    return rows


def validate_provenance_sidecar(sidecar: pd.DataFrame, preds: dict, *,
                                fold_id: str, config_hash: str,
                                snapshot_hash: str) -> dict:
    """The v8 sidecar validator — same clauses as v7's, bound to the v8 arm."""
    problems: list[str] = []
    try:
        missing = [c for c in SIDECAR_COLS if c not in sidecar.columns]
        if missing:
            return {"receipt": "provenance_history/1", "ok": False,
                    "problems": [f"sidecar missing columns: {missing}"]}
        if (sidecar["schema"] != PROVENANCE_SIDECAR_SCHEMA).any():
            problems.append(f"sidecar schema is not {PROVENANCE_SIDECAR_SCHEMA!r}")
        if (sidecar["arm_id"] != ARM_ID).any():
            problems.append(f"sidecar arm_id is not uniformly {ARM_ID!r}")
        if (sidecar["fold_id"] != fold_id).any():
            problems.append(f"sidecar fold_id is not uniformly {fold_id!r}")
        if (sidecar["config_hash"].astype(str) != config_hash).any():
            problems.append("sidecar config_hash does not match the run")
        if (sidecar["data_snapshot_hash"].astype(str) != snapshot_hash).any():
            problems.append("sidecar data_snapshot_hash does not match the run")
        if sidecar.duplicated(subset=["target_key", "row_uid"]).any():
            problems.append(
                f"{int(sidecar.duplicated(subset=['target_key', 'row_uid']).sum())} "
                f"duplicate (target_key, row_uid) provenance rows")

        for tgt, p in preds.items():
            sub = sidecar[sidecar.target_key == tgt]
            if len(sub) != len(p):
                problems.append(f"{tgt}: sidecar has {len(sub)} rows for "
                                f"{len(p)} predictions")
            if set(sub.row_uid) != set(p.row_uid):
                problems.append(f"{tgt}: sidecar row_uid set does not equal the "
                                f"prediction row_uid set")
                continue
            j = p[["row_uid", "component_id", "fallback_level", "feature_asof",
                   "forecast_cutoff"]].merge(
                sub[["row_uid", "component_id", "fallback_level", "feature_asof",
                     "forecast_cutoff"]], on="row_uid", suffixes=("", "__sc"))
            for c in ("component_id", "fallback_level", "feature_asof",
                      "forecast_cutoff"):
                bad = int((j[c].astype(str) != j[f"{c}__sc"].astype(str)).sum())
                if bad:
                    problems.append(f"{tgt}: {bad} rows where sidecar {c} disagrees "
                                    f"with the emitted prediction")
        extra = set(sidecar.target_key) - set(preds)
        if extra:
            problems.append(f"sidecar carries targets not emitted: {sorted(extra)}")

        lvl = pd.to_numeric(sidecar.fallback_level, errors="coerce")
        if lvl.isna().any() or (lvl % 1 != 0).any() or (lvl < 0).any() \
                or (lvl > MAX_FALLBACK_LEVEL).any():
            problems.append(f"fallback_level must be an integer 0..{MAX_FALLBACK_LEVEL}")
        rp = pd.to_numeric(sidecar.residual_pool_n, errors="coerce")
        if rp.isna().any() or (rp % 1 != 0).any() or (rp < -1).any():
            problems.append("residual_pool_n must be an integer >= -1")

        cand = pd.to_numeric(sidecar.n_prior_candidate_games, errors="coerce")
        app = pd.to_numeric(sidecar.n_prior_appearances, errors="coerce")
        avail = pd.to_numeric(sidecar.n_prior_available_obligations, errors="coerce")
        have = cand.notna() & app.notna()
        if have.any() and (app[have] > cand[have]).any():
            problems.append("prior appearances exceed prior candidate obligations")
        have2 = app.notna() & avail.notna()
        if have2.any() and (app[have2] > avail[have2]).any():
            problems.append("prior appearances exceed AVAILABLE prior obligations; "
                            "an appearance was counted from an outcome that was not "
                            "yet knowable")
        for c in ("n_prior_candidate_games", "n_prior_appearances",
                  "n_prior_available_obligations", "team_prior_games"):
            v = pd.to_numeric(sidecar[c], errors="coerce")
            if (v.dropna() < 0).any():
                problems.append(f"{c} must be non-negative where present")

        src = set(pd.unique(sidecar.outcome_availability_source))
        if not src <= {"observed", "policy"}:
            problems.append(f"unexpected outcome_availability_source values: "
                            f"{sorted(src - {'observed', 'policy'})}")
        if "policy" in src:
            pol = sidecar.loc[sidecar.outcome_availability_source == "policy",
                              "outcome_availability_policy_id"]
            if (pol.astype(str) != OUTCOME_AVAILABILITY_POLICY_ID).any():
                problems.append("policy-derived availability rows must name the "
                                "registered policy id")
        if "observed" in src:
            pol = sidecar.loc[sidecar.outcome_availability_source == "observed",
                              "outcome_availability_policy_id"]
            if (pol.astype(str) != "").any():
                problems.append("observed availability rows must NOT carry a policy "
                                "id; a policy timestamp is not an observation")

        return {"receipt": "provenance_history/1", "ok": not problems,
                "problems": problems, "schema": PROVENANCE_SIDECAR_SCHEMA,
                "n_rows": int(len(sidecar)), "digest": sidecar_digest(sidecar),
                "targets": sorted(set(sidecar.target_key))}
    except Exception as exc:                       # fail closed, never raise
        return {"receipt": "provenance_history/1", "ok": False,
                "problems": [f"sidecar validator raised {type(exc).__name__}: {exc}"]}


# --------------------------------------------------------------------------
# 5. player fold
# --------------------------------------------------------------------------

def run_player_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                    config_hash: str, snapshot_hash: str,
                    snapshot_manifest: dict | None = None, universe=None,
                    synthetic: bool = True,
                    allow_declared_defaults: bool | None = None,
                    artifact_root: Path | str | None = None,
                    registry_path: Path | str = REGISTRY_PATH) -> dict:
    """All four player targets, with provenance receipted on EVERY frame read."""
    # Identity and frame binding run FIRST, before any split, selection or fit,
    # so a mutated frame cannot reach a coefficient.
    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    config_hash = identity["config_hash"]
    snapshot_hash = identity["snapshot_hash"]

    if allow_declared_defaults is None:
        allow_declared_defaults = bool(synthetic)
    if not synthetic and allow_declared_defaults:
        raise AdapterBoundaryError(
            "declared Stage-A defaults are forbidden on the real path; every "
            "registered input must actually be supplied")

    fold = require_outer_fold(train, test, fold_id)
    train = order_obligations(train) if len(train) else train
    test = order_obligations(test)

    # ---- source provenance on BOTH frames  (blocker 1) --------------------
    feature_asof, src = resolve_fold_sources(
        train, test, REQUIRED_PLAYER_FEATURE_SOURCES, synthetic=synthetic)
    prov_src = source_provenance_receipt(src, synthetic=synthetic)

    combined = combine_history_frames(train, test)
    if "appeared" not in combined.columns:
        combined["appeared"] = np.nan

    plan_all = build_walk_forward_plan(combined, group_cols=["player_id", "season"],
                                       sort_cols=list(PLAYER_SORT_KEYS))
    hist_all = player_history_walk_forward(combined, plan_all)
    hist_by_uid = hist_all.set_axis(combined["row_uid"].to_numpy(), axis=0)
    hist_te = hist_by_uid.reindex(test["row_uid"].to_numpy()).set_axis(test.index, axis=0)
    hist_tr = (hist_by_uid.reindex(train["row_uid"].to_numpy())
               .set_axis(train.index, axis=0) if len(train) else None)

    avail_src, policy_id = plan_all.availability_source, plan_all.policy_id
    diag: dict = {"fold_id": fold_id, "selected": {}, "dispersion": {},
                  "fallback_mean": {}, "fitted_state": {}, "fold_boundary": fold,
                  "availability": {"source": avail_src, "policy_id": policy_id},
                  "source_provenance": prov_src,
                  "walk_forward": {
                      "n_rows": int(len(combined)),
                      "mean_admitted_prior": float(np.mean(plan_all.n_admitted)),
                      "max_admitted_prior": int(np.max(plan_all.n_admitted))}}

    ctx = (player_split(train) if len(train) else
           SplitContext(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                        degenerate=True, reason="empty training window", label="player"))
    diag["degenerate"], diag["reason"] = ctx.degenerate, ctx.reason

    preds: dict[str, pd.DataFrame] = {}
    prov: list[pd.DataFrame] = []
    no_excl = pd.Series(pd.NA, index=test.index)
    hist_flat = hist_te.reset_index(drop=True)

    def record(tgt, pred, alpha, lam, npool):
        preds[tgt] = pred
        prov.append(_provenance_rows(
            pred, target=tgt, fold_id=fold_id, config_hash=config_hash,
            snapshot_hash=snapshot_hash, selected_alpha=alpha, selected_lambda=lam,
            residual_pool_n=npool, hist=hist_flat, team_prior=None,
            availability_source=avail_src, policy_id=policy_id))

    if ctx.degenerate or len(train) == 0:
        for tgt in PLAYER_TARGETS:
            d = DECLARED[tgt]
            sd = d.get("sd")
            comp = f"{tgt}/declared_constant"
            st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                             fallback_mean=d["point"], dispersion_sd=sd,
                             dispersion_method="declared",
                             availability_source=avail_src,
                             availability_policy_id=policy_id,
                             support={"low": d.get("low"), "high": d.get("high")})
            n_prior = hist_te["n_prior_appearances"]
            lvl = player_fallback_level(test, n_prior,
                                        pd.Series(True, index=test.index),
                                        degenerate=True)
            record(tgt, _emit(
                test, tgt, pd.Series(d["point"], index=test.index),
                pd.Series(sd, index=test.index) if sd else None,
                (np.asarray(QUANTILE_Z) * sd) if sd else None,
                fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
                model_hash=st.hash(), feature_asof=feature_asof, fallback_level=lvl,
                component_id=pd.Series(comp, index=test.index),
                is_cold=pd.Series(True, index=test.index), n_prior=n_prior,
                exclusion=no_excl, low=d.get("low"), high=d.get("high"),
                want_q=(tgt != "p_active")), None, None, None)
            diag["fitted_state"][tgt] = st.to_dict()
        diag["fallback"] = "declared_constants"
        return _finish(preds, pd.concat(prov, ignore_index=True), diag, universe,
                       fold_id, config_hash, snapshot_hash, fold, identity, prov_src)

    tuning_mask = pd.Series(False, index=train.index)
    tuning_mask.loc[ctx.tuning_idx] = True
    active_any = train["appeared"].astype(bool)
    all_tune, active_tune = tuning_mask, tuning_mask & active_any

    base_rate = prefix_mean(train["appeared"].astype(float), ctx, all_tune)
    Xtr = stage_a_features_v8(train, hist_tr, base_rate,
                              allow_declared_defaults=allow_declared_defaults)
    Xte = stage_a_features_v8(test, hist_te, base_rate,
                              allow_declared_defaults=allow_declared_defaults)
    from cbs_v5 import select_lambda_chronological
    lam, lam_default, inner = select_lambda_chronological(
        Xtr, train["appeared"].astype(float), ctx, train)
    tr_idx = ctx.require_tuning(np.asarray(train.index[all_tune]))
    std = Standardizer(Xtr.loc[tr_idx])
    beta = logistic_fit(std.transform(Xtr.loc[tr_idx]),
                        train["appeared"].reindex(tr_idx).to_numpy(float), lam)
    p_hat = pd.Series(logistic_predict(std.transform(Xte), beta), index=test.index)

    comp_pa = "p_active/ridge_logistic_stage_a"
    st_pa = FittedState(target="p_active", fold_id=fold_id, component_id=comp_pa,
                        feature_order=list(P_ACTIVE_FEATURES),
                        scaler_mean=std.mean.tolist(), scaler_std=std.std.tolist(),
                        dropped_features=list(std.dropped), lam=lam,
                        beta=np.round(beta, 12).tolist(), base_rate=base_rate,
                        availability_source=avail_src, availability_policy_id=policy_id,
                        support={"low": 0.0, "high": 1.0})
    diag["selected"].update({"lambda": lam, "lambda_default": lam_default,
                             "lambda_inner_fit_dates": len(inner.fit_dates),
                             "lambda_inner_val_dates": len(inner.val_dates)})
    diag["base_rate"] = base_rate
    diag["fitted_state"]["p_active"] = st_pa.to_dict()

    n_oblig = hist_te["n_prior_candidate_games"]
    lvl_pa = player_fallback_level(test, n_oblig, np.isfinite(p_hat))
    comp_col_pa = pd.Series(comp_pa, index=test.index).mask(
        lvl_pa > 0, "p_active/declared_constant")
    record("p_active", _emit(
        test, "p_active", p_hat.where(lvl_pa == 0, DECLARED["p_active"]["point"]),
        None, None, fold_id=fold_id, config_hash=config_hash,
        snapshot_hash=snapshot_hash, model_hash=st_pa.hash(),
        feature_asof=feature_asof, fallback_level=lvl_pa, component_id=comp_col_pa,
        is_cold=~hist_te["has_prior_obligation"],
        n_prior=hist_te["n_prior_appearances"], exclusion=no_excl,
        low=0.0, high=1.0, want_q=False), None, lam, None)

    plan_tr = build_walk_forward_plan(train, group_cols=["player_id", "season"],
                                      sort_cols=list(PLAYER_SORT_KEYS))
    act_tr = train["appeared"].astype(bool)

    def minutes_pred(a):
        return walk_forward_ewma(plan_tr, train["minutes"], a, mask=act_tr)

    m_alpha, _, m_b = select_alpha_bound(minutes_pred, train["minutes"], ctx, active_tune)

    def attempts_pred(a):
        return conditional_center(plan_tr, train, act_tr, "attempts_usage",
                                  minutes_alpha=m_alpha, rate_alpha=a)

    def points_pred(a):
        return conditional_center(plan_tr, train, act_tr,
                                  "player_scoring_distribution",
                                  minutes_alpha=m_alpha, rate_alpha=a)

    a_alpha, _, a_b = select_alpha_bound(attempts_pred, train["fga"], ctx, active_tune)
    p_alpha, _, p_b = select_alpha_bound(points_pred, train["points"], ctx, active_tune)
    diag["selected"].update({"minutes_alpha": m_alpha, "attempts_alpha": a_alpha,
                             "points_alpha": p_alpha,
                             "minutes_alpha_held_fixed_at": m_alpha,
                             "boundaries": {"minutes": m_b, "attempts": a_b,
                                            "points": p_b}})

    act_all = combined["appeared"].astype(float).fillna(0.0).astype(bool)

    def _center(alpha_rate, tgt):
        s = conditional_center(plan_all, combined, act_all, tgt,
                               minutes_alpha=m_alpha, rate_alpha=alpha_rate)
        return (pd.Series(s.to_numpy(), index=combined["row_uid"].to_numpy())
                .reindex(test["row_uid"].to_numpy()).set_axis(test.index))

    for tgt, alpha, ycol, tr_fn in (
            ("e_minutes_given_active", m_alpha, "minutes",
             lambda: walk_forward_ewma(plan_tr, train["minutes"], m_alpha, mask=act_tr)),
            ("attempts_usage", a_alpha, "fga", lambda: attempts_pred(a_alpha)),
            ("player_scoring_distribution", p_alpha, "points",
             lambda: points_pred(p_alpha))):
        d = DECLARED[tgt]
        fb_mean = prefix_mean(train[ycol].astype(float), ctx, active_tune)
        if not np.isfinite(fb_mean):
            fb_mean = d["point"]
        diag["fallback_mean"][tgt] = fb_mean

        cal = np.intersect1d(ctx.calibration_idx, np.asarray(train.index[act_tr]))
        sd_v, off, method = dispersion(
            residuals(train[ycol].reindex(cal), tr_fn().reindex(cal)),
            min_resid=MIN_RESID_PLAYER)
        if method == "insufficient":
            sd_v = d["sd"]
            off = np.asarray(QUANTILE_Z) * sd_v
        diag["dispersion"][tgt] = {"method": method, "sd": float(sd_v),
                                   "n_resid": int(len(cal))}

        raw = _center(alpha, tgt)
        n_prior = hist_te["n_prior_appearances"]
        lvl = player_fallback_level(test, n_prior, np.isfinite(raw))
        comp = f"{tgt}/walk_forward_active_ewma"
        comp_col = pd.Series(comp, index=test.index).mask(lvl > 0, f"{tgt}/prefix_mean")

        st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                         alphas={"minutes": m_alpha, "attempts": a_alpha,
                                 "points": p_alpha},
                         fallback_mean=fb_mean, dispersion_sd=float(sd_v),
                         dispersion_method=method,
                         dispersion_offsets=np.round(off, 12).tolist(),
                         residual_pool_n=int(len(cal)),
                         availability_source=avail_src, availability_policy_id=policy_id,
                         support={"low": d.get("low"), "high": d.get("high")})
        diag["fitted_state"][tgt] = st.to_dict()
        record(tgt, _emit(
            test, tgt, raw.where(lvl == 0, fb_mean),
            pd.Series(sd_v, index=test.index), off, fold_id=fold_id,
            config_hash=config_hash, snapshot_hash=snapshot_hash,
            model_hash=st.hash(), feature_asof=feature_asof, fallback_level=lvl,
            component_id=comp_col, is_cold=~hist_te["has_prior_appearance"],
            n_prior=n_prior, exclusion=no_excl, low=d.get("low"), high=d.get("high"),
            want_q=True), alpha, None, int(len(cal)))

    return _finish(preds, pd.concat(prov, ignore_index=True), diag, universe,
                   fold_id, config_hash, snapshot_hash, fold, identity, prov_src)


# --------------------------------------------------------------------------
# 6. team fold
# --------------------------------------------------------------------------

def run_team_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                  config_hash: str, snapshot_hash: str,
                  snapshot_manifest: dict | None = None, universe=None,
                  synthetic: bool = True,
                  artifact_root: Path | str | None = None,
                  registry_path: Path | str = REGISTRY_PATH) -> dict:
    """The team target. `test` is a CURRENT OBLIGATION frame: no outcomes needed."""
    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    config_hash = identity["config_hash"]
    snapshot_hash = identity["snapshot_hash"]

    require_team_history_inputs(train)
    require_team_current_obligations(test)
    fold = require_outer_fold(train, test, fold_id)

    feature_asof, src = resolve_fold_sources(
        train, test, REQUIRED_TEAM_FEATURE_SOURCES, synthetic=synthetic)
    prov_src = source_provenance_receipt(src, synthetic=synthetic)

    d = DECLARED[TEAM_TARGET]
    tgt = TEAM_TARGET

    combined = combine_history_frames(train, test)
    usable = team_history_usable(combined)

    plan_all = build_walk_forward_plan(combined, group_cols=list(TEAM_HISTORY_GROUP),
                                       sort_cols=list(TEAM_SORT_KEYS))
    plan_tr = build_walk_forward_plan(train, group_cols=list(TEAM_HISTORY_GROUP),
                                      sort_cols=list(TEAM_SORT_KEYS))
    avail_src, policy_id = plan_all.availability_source, plan_all.policy_id

    # prior_games counts only COMPLETE, available observations, so MIN_PRIOR
    # cannot be satisfied by rows that never reached the average.
    prior_all = walk_forward_counts(plan_all, mask=usable).reindex(combined.index)
    prior_by_uid = pd.Series(prior_all.to_numpy(), index=combined["row_uid"].to_numpy())
    prior_te = prior_by_uid.reindex(test["row_uid"].to_numpy()).set_axis(test.index)
    prior_tr = walk_forward_counts(
        plan_tr, mask=team_history_usable(train)).reindex(train.index)

    diag: dict = {"fold_id": fold_id, "fold_boundary": fold,
                  "availability": {"source": avail_src, "policy_id": policy_id},
                  "source_provenance": prov_src,
                  "team_min_prior": TEAM_MIN_PRIOR,
                  "current_obligations_require_outcomes": False,
                  "n_test_with_channels_present": int(
                      team_history_usable(test).sum()),
                  "n_test_below_min_prior": int((prior_te < TEAM_MIN_PRIOR).sum()),
                  "n_train_eligible_for_selection": int(
                      (prior_tr >= TEAM_MIN_PRIOR).sum())}
    ts = team_split(train)
    diag["degenerate"], diag["reason"] = ts.degenerate, ts.reason
    diag["segment_dates"] = {"T1": len(ts.t1_dates), "T2": len(ts.t2_dates),
                             "T3": len(ts.t3_dates)}
    diag["zero_candidate_team_games"] = int(
        test.get("n_candidates", pd.Series(1, index=test.index)).eq(0).sum())
    no_excl = pd.Series(pd.NA, index=test.index)
    prior_flat = prior_te.reset_index(drop=True)

    def finish_one(pred, alpha, npool):
        sidecar = _provenance_rows(
            pred, target=tgt, fold_id=fold_id, config_hash=config_hash,
            snapshot_hash=snapshot_hash, selected_alpha=alpha, selected_lambda=None,
            residual_pool_n=npool, hist=None, team_prior=prior_flat,
            availability_source=avail_src, policy_id=policy_id)
        return _finish({tgt: pred}, sidecar, diag, universe, fold_id, config_hash,
                       snapshot_hash, fold, identity, prov_src)

    if ts.degenerate:
        comp = f"{tgt}/declared_constant"
        st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                         fallback_mean=d["point"], dispersion_sd=d["sd"],
                         dispersion_method="declared", min_prior=TEAM_MIN_PRIOR,
                         availability_source=avail_src, availability_policy_id=policy_id,
                         support={"low": d["low"]})
        lvl = team_fallback_level(test, prior_te, pd.Series(True, index=test.index),
                                  degenerate=True)
        diag["fitted_state"] = {tgt: st.to_dict()}
        diag["fallback"] = "declared_constants"
        return finish_one(_emit(
            test, tgt, pd.Series(d["point"], index=test.index),
            pd.Series(d["sd"], index=test.index), np.asarray(QUANTILE_Z) * d["sd"],
            fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
            model_hash=st.hash(), feature_asof=feature_asof, fallback_level=lvl,
            component_id=pd.Series(comp, index=test.index),
            is_cold=(prior_te == 0), n_prior=prior_te, exclusion=no_excl,
            low=d["low"], high=None, want_q=True), None, None)

    eligible = prior_tr >= TEAM_MIN_PRIOR
    ctx1 = ts.context_for_alpha()
    t1_mask = pd.Series(False, index=train.index)
    t1_mask.loc[ts.t1] = True
    sel_mask = t1_mask & eligible
    alphas: dict[str, float] = {}
    for ch in REQUIRED_CHANNELS:
        def chan_pred(a, ch=ch):
            return walk_forward_ewma(plan_tr, train[f"ch_{ch}"], a,
                                     mask=team_history_usable(train))
        alphas[ch], _, _ = select_alpha_bound(chan_pred, train[f"ch_{ch}"],
                                              ctx1, sel_mask, grid=ALPHA_GRID)
    diag["channel_alphas"] = alphas
    diag["n_selection_rows"] = int(sel_mask.sum())

    def structural(plan, frame, mask):
        total = None
        for ch in REQUIRED_CHANNELS:
            col = (frame[f"ch_{ch}"] if f"ch_{ch}" in frame.columns
                   else pd.Series(np.nan, index=frame.index))
            s = walk_forward_ewma(plan, col, alphas[ch], mask=mask)
            total = s if total is None else total + s
        return total

    ctx2 = ts.context_for_calibration_map()
    struct_tr = structural(plan_tr, train, team_history_usable(train))
    map_idx = np.intersect1d(np.asarray(ctx2.tuning_idx),
                             np.asarray(train.index[eligible]))
    maps = fit_side_maps(train, struct_tr, map_idx)
    diag["calibration_maps"] = maps
    diag["n_calibration_map_rows"] = int(len(map_idx))

    fitted = apply_side_maps(train, struct_tr, maps)
    t3_idx = np.intersect1d(np.asarray(ts.t3), np.asarray(train.index[eligible]))
    sd_v, off, method = dispersion(
        residuals(train["team_points"].reindex(t3_idx), fitted.reindex(t3_idx)),
        min_resid=MIN_RESID_TEAM)
    if method == "insufficient":
        sd_v = d["sd"]
        off = np.asarray(QUANTILE_Z) * sd_v
    diag["dispersion"] = {"method": method, "sd": float(sd_v),
                          "n_resid": int(len(t3_idx))}

    struct_all = structural(plan_all, combined, usable)
    struct_te = (pd.Series(struct_all.to_numpy(), index=combined["row_uid"].to_numpy())
                 .reindex(test["row_uid"].to_numpy()).set_axis(test.index))
    raw = apply_side_maps(test, struct_te, maps)

    lvl = team_fallback_level(test, prior_te, np.isfinite(raw))
    comp = f"{tgt}/walk_forward_channel_ewma_side_map"
    comp_col = pd.Series(comp, index=test.index).mask(lvl > 0, f"{tgt}/declared_constant")

    st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                     alphas=dict(alphas),
                     calibration_maps={k: list(v) for k, v in maps.items()},
                     fallback_mean=d["point"], dispersion_sd=float(sd_v),
                     dispersion_method=method,
                     dispersion_offsets=np.round(off, 12).tolist(),
                     residual_pool_n=int(len(t3_idx)), min_prior=TEAM_MIN_PRIOR,
                     availability_source=avail_src, availability_policy_id=policy_id,
                     support={"low": d["low"]})
    diag["fitted_state"] = {tgt: st.to_dict()}
    return finish_one(_emit(
        test, tgt, raw.where(lvl == 0, d["point"]),
        pd.Series(sd_v, index=test.index), off, fold_id=fold_id,
        config_hash=config_hash, snapshot_hash=snapshot_hash, model_hash=st.hash(),
        feature_asof=feature_asof, fallback_level=lvl, component_id=comp_col,
        is_cold=(prior_te == 0), n_prior=prior_te, exclusion=no_excl,
        low=d["low"], high=None, want_q=True), None, int(len(t3_idx)))


# --------------------------------------------------------------------------
# 7. the composite gate — now EIGHT receipts
# --------------------------------------------------------------------------

def _finish(preds, sidecar, diag, universe, fold_id, config_hash, snapshot_hash,
            fold_receipt, identity_receipt, source_receipt) -> dict:
    """Every named receipt, then and only then `scoring_permitted`."""
    receipts = {
        "identity_binding": identity_receipt,
        "frame_binding": identity_receipt["frame_binding"],
        "source_provenance": source_receipt,
        "fold_boundary": fold_receipt,
    }
    prov = validate_provenance_sidecar(sidecar, preds, fold_id=fold_id,
                                       config_hash=config_hash,
                                       snapshot_hash=snapshot_hash)
    receipts["provenance_history"] = prov

    prediction: dict = {}
    if universe is not None:
        for tgt, p in preds.items():
            prediction[tgt] = validate_arm_output_v3(
                p, universe, tgt, expected_arm_id=ARM_ID, expected_fold_id=fold_id,
                expected_config_hash=config_hash, expected_snapshot_hash=snapshot_hash)
        receipts["prediction_validation"] = {
            "receipt": "prediction_validation/1",
            "ok": all(r["ok"] for r in prediction.values()) and bool(prediction),
            "problems": [f"{t}: {p}" for t, r in prediction.items()
                         for p in r.get("problems", [])],
            "per_target": prediction}
        receipts["exclusion_crosstab"] = exclusion_receipt(preds, universe)
        receipts["coverage"] = coverage_receipt(preds, universe)
    else:
        for name in ("prediction_validation", "exclusion_crosstab", "coverage"):
            receipts[name] = {"receipt": name, "ok": False,
                              "problems": ["no universe supplied; this receipt "
                                           "cannot be produced, so it does not pass"]}

    required = ("identity_binding", "frame_binding", "source_provenance",
                "fold_boundary", "provenance_history", "prediction_validation",
                "exclusion_crosstab", "coverage")
    failed = [n for n in required if not receipts.get(n, {}).get("ok")]
    permitted = not failed

    return {
        "arm_id": ARM_ID, "fold_id": fold_id,
        "predictions": preds, "provenance_sidecar": sidecar,
        "provenance_sidecar_digest": prov.get("digest"),
        "diagnostics": diag, "receipts": receipts,
        "validation_receipts": prediction,
        "coverage": receipts["coverage"].get("per_target", {}),
        "required_receipts": list(required), "failed_receipts": failed,
        "validated": permitted, "scoring_permitted": permitted,
        "scoring_note": "scoring_permitted requires EVERY named receipt to pass; "
                        "this runner computes no accuracy or coverage score in any "
                        "case and reads no file but the registry and, when an "
                        "artifact_root is given, the snapshot artifacts it verifies",
    }
