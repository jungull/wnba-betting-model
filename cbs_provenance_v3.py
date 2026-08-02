#!/usr/bin/env python3
"""cbs_provenance_v3.py — `cbs_provenance/3`: exactly five artifacts, or nothing.

WHAT `/2` GOT RIGHT AND IS KEPT HERE
------------------------------------
`cbs_provenance.py` (`/2`, frozen under `contract_baseline_suite_v9`) fixed three
real defects and those fixes are **reused, not restated** — a duplicated audit is
an audit that will eventually disagree with itself:

* **ALL-required column semantics.** `bool(["minutes"])` is True, so v8's
  `bool(any present)` reported a frame supplying one of fourteen features as
  supplying the feature set. `/2` requires every registered field and names what
  is missing; `schema_status` and `feature_availability` are imported unchanged.
* **Hard blockers separated from carried policy limitations.** An unattested
  artifact can be fixed; the absence of a historical observation that was never
  recorded cannot. Filing the second under "blocking" implies a repair that would
  have to be fabricated. The split, and `ACCEPTED_POLICY_LIMITATIONS`, are kept.
* **`provenance_preconditions_met`, never `real_run_permitted`.** Clearing the
  checks means the provenance preconditions hold. It is not permission to run.
* **Attestation over all five artifacts**, with the enforced list identical to
  the documented one.

WHAT `/2` STILL GOT WRONG
-------------------------
**The five-artifact rule was a DEFAULT, not a requirement.** `/2`'s
`build_snapshot_manifest` takes `artifacts=CBS_REQUIRED_ARTIFACTS` as a plain
default, so::

    prov.build_snapshot_manifest(frames, artifacts=(prov.PLAYER_GAME,))

builds a perfectly valid one-artifact manifest, and `cbs_v9.snapshot_identity`
accepts it — its only artifact check is "at least one entry, each a 64-hex
digest". Every downstream receipt then reports success while four of the five
consumed artifacts were never hashed, never attested and never named. The audit
said "all five are enforced"; the manifest builder let the caller choose.

A default is a suggestion. `/3` makes it **exact key equality**: the manifest's
artifact set must equal `CBS_REQUIRED_ARTIFACTS` — no subsets, and no supersets
either. A superset matters as much as a subset: an extra artifact silently widens
the snapshot identity to cover a file no reviewer agreed was an input, so two
runs over the same five inputs get different identities depending on what else
happened to be listed.

`/3` also adds a check `/2` had no notion of: **every artifact's `fit_through_date`
must follow the convention it declares.** Four of the five CBS inputs derived
their bound from `asof_invariant.bound_from_dates`; `player_game.parquet` carried
`max(game_date)` read as MIDNIGHT, which sits BEFORE the games played that day —
the anti-conservative reading `bound_from_dates` exists to prevent. A bound that
is EARLIER than the convention's is a hard blocker. A bound that is LATER is
conservative and merely reported, because being over-cautious about as-of is
never wrong in the unsafe direction.

THE TEST-ONLY ESCAPE, AND WHY A REAL RUN CANNOT REACH IT
---------------------------------------------------------
Synthetic suites must be able to build manifests over fixture trees that do not
contain the five real artifacts. That need is met by
`build_snapshot_manifest(..., synthetic=True, _test_artifacts=(...))`, and it is
constructed so that a real-path caller cannot arrive there by accident:

1. **The real entry point has no artifact parameter at all.**
   `build_real_snapshot_manifest(frames, root=...)` takes no `artifacts`, no
   `_test_artifacts`, no `synthetic` and no `**kwargs`. There is no argument a
   real caller could mistype into an escape, because there is no argument.
2. **Both escape parameters are keyword-only.** No positional call can reach
   them, so an extra positional argument is a `TypeError`, not a bypass.
3. **Two independent tokens are required and each is inert alone.**
   `_test_artifacts=` without `synthetic=True` is rejected OUTRIGHT — it does not
   fall back to the five, it raises. And `synthetic=True` on its own changes
   nothing: the exact-five rule still applies. So neither a single flipped
   default, nor a single stray key in a forwarded `**kwargs`, nor a single typo
   opens the escape; it takes two deliberate, disagreeing-with-the-default acts.
4. **The leading underscore is a name no ordinary caller writes**, and it is
   never read from a config file, an environment variable or a CLI flag. The CLI
   in this module cannot set it.
5. **The escape LABELS its own output.** A manifest built through it carries
   `synthetic: True` and `real_path_permitted: False`, and
   `require_real_snapshot_manifest` refuses any manifest carrying that stamp. So
   even a manifest built through the escape cannot be laundered into a real run
   downstream — the refusal does not depend on remembering how it was made.

FRAME IDENTITY
--------------
Manifests emitted here declare `frame_identity_schema = "cbs_frame_identity/3"`
and their frame digests come from `cbs_identity_v3` in its default scalar-only
mode. `cbs_v9` is bound to `/2` and will therefore REFUSE these manifests. That
is deliberate and is the same stance v9 took toward `/2` manifests: a runner must
not accept an identity computed under an encoding it has not been checked
against. The two cannot be confused, because `snapshot_identity` compares the
declared `frame_identity_schema` exactly, and because a `/3` frame digest of the
same frame is a different string from its `/2` digest.

**This module fits nothing, predicts nothing and scores nothing.** Every value it
produces is a path, a column name, a byte count, a hash, a count, a timestamp
bound or a boolean.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import asof_invariant as aoi
import cbs_provenance as _p2
from cbs_identity_v3 import (FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE,
                             frames_digest)
# Reconciled at fan-in by the coordinator: the manifest schema must move in
# lockstep with the frame-identity generation, so /4 belongs with
# cbs_frame_identity/3. Importing v9's /3 here would have emitted manifests
# whose schema number claimed an identity encoding they no longer used.
from cbs_v10 import SNAPSHOT_MANIFEST_SCHEMA

PROVENANCE_ID = "cbs_provenance/3"
AUDIT_SCHEMA = "cbs_real_input_audit/3"
SUPERSEDES = _p2.PROVENANCE_ID

REPO_ROOT = _p2.REPO_ROOT
CONTRACT_DIR = _p2.CONTRACT_DIR

# --- the artifact identities, re-exported unchanged from /2 ----------------
PLAYER_GAME = _p2.PLAYER_GAME
TEAM_GAME = _p2.TEAM_GAME
CONTRACT_JSON = _p2.CONTRACT_JSON
MASTER_PLAYER = _p2.MASTER_PLAYER
MASTER_TEAM = _p2.MASTER_TEAM

# Reconciled at fan-in by the coordinator. The row universe moved to
# prediction_contract_v3 (the v2 candidate lookback was positional, not
# availability-causal), so the artifacts a real v10 run consumes are the V3
# contract trio plus the two masters. Importing v2's tuple here would have
# enforced "exactly five" against the superseded universe -- the check would have
# passed while binding the wrong contract.
CONTRACT_DIR_V3 = "experiments/prediction_contract_v3"
PLAYER_GAME_V3 = f"{CONTRACT_DIR_V3}/player_game.parquet"
TEAM_GAME_V3 = f"{CONTRACT_DIR_V3}/team_game.parquet"
CONTRACT_JSON_V3 = f"{CONTRACT_DIR_V3}/contract.json"

CBS_REQUIRED_ARTIFACTS = (PLAYER_GAME_V3, TEAM_GAME_V3, CONTRACT_JSON_V3,
                          _p2.MASTER_PLAYER, _p2.MASTER_TEAM)
#: the superseded v2 set, retained so the supersession is auditable rather than
#: implied by absence
CBS_REQUIRED_ARTIFACTS_V2_SUPERSEDED = _p2.CBS_REQUIRED_ARTIFACTS

# Canonical per-artifact names for the v10 set, so callers refer to "the contract
# this arm consumes" rather than to a version number they then have to keep in
# sync. Anything importing these gets the v3 contract without further edits.
PLAYER_GAME = PLAYER_GAME_V3
TEAM_GAME = TEAM_GAME_V3
CONTRACT_JSON = CONTRACT_JSON_V3
CONTRACT_DIR = CONTRACT_DIR_V3
MASTER_PLAYER = _p2.MASTER_PLAYER
MASTER_TEAM = _p2.MASTER_TEAM
attest_artifact = _p2.attest_artifact
ProvenancePreconditionError = _p2.ProvenancePreconditionError
# Reconciled at fan-in: this MUST track the v3 required set, not v2's. Leaving
# it pointing at the superseded tuple would have enforced attestation on the
# old contract while the exact-five check ran against the new one -- the two
# lists would have disagreed silently. Caught by test C.
MUST_BE_ATTESTED = CBS_REQUIRED_ARTIFACTS
N_REQUIRED_ARTIFACTS = len(CBS_REQUIRED_ARTIFACTS)

# --- the /2 behaviour that was correct, imported rather than copied --------
REQUIRED_COLUMNS = _p2.REQUIRED_COLUMNS
RUNNER_DERIVED_FEATURES = _p2.RUNNER_DERIVED_FEATURES
ADAPTER_DERIVED_FEATURES = _p2.ADAPTER_DERIVED_FEATURES
ACCEPTED_POLICY_LIMITATIONS = _p2.ACCEPTED_POLICY_LIMITATIONS

ProvenancePreconditionError = _p2.ProvenancePreconditionError
artifact_sha256 = _p2.artifact_sha256
attestation_status = _p2.attestation_status
schema_status = _p2.schema_status
feature_availability = _p2.feature_availability
attest_artifact = _p2.attest_artifact

# --- bound convention ------------------------------------------------------
#: the one convention every CBS input must declare and follow
BOUND_CONVENTION = "asof_invariant.bound_from_dates"

#: artifacts that carry their own `game_date` and must derive their bound from it
DATE_BEARING_ARTIFACTS = (PLAYER_GAME, TEAM_GAME, MASTER_PLAYER, MASTER_TEAM)
#: artifacts with no dates of their own, whose bound is inherited from the above
INHERITED_BOUND_ARTIFACTS = (CONTRACT_JSON,)


class ArtifactSetError(ProvenancePreconditionError):
    """The manifest's artifact set is not exactly `CBS_REQUIRED_ARTIFACTS`.

    A subclass of `ProvenancePreconditionError` so that every existing caller
    that already catches provenance failures catches this one too — a new failure
    mode that slips past old handlers is a new way to run unnoticed.
    """


class BoundConventionError(ProvenancePreconditionError):
    """An artifact's `fit_through_date` does not follow the convention it declares."""


class TestEscapeMisuse(ProvenancePreconditionError):
    """The synthetic-only artifact override was reached without its second token."""


# --------------------------------------------------------------------------
# exact five, enforced by key equality
# --------------------------------------------------------------------------

def require_exact_artifact_set(artifacts, *, where: str = "snapshot manifest") -> tuple:
    """The artifact set must EQUAL `CBS_REQUIRED_ARTIFACTS`. Both directions.

    Returns the canonical tuple on success. Names both what is missing and what
    is extra, because "the sets differ" is not an actionable message.
    """
    try:
        got = set(artifacts)
    except TypeError as exc:
        raise ArtifactSetError(
            f"{where}: artifacts must be an iterable of paths; got "
            f"{type(artifacts).__name__}") from exc
    want = set(CBS_REQUIRED_ARTIFACTS)
    missing = sorted(want - got)
    extra = sorted(got - want)
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"MISSING {len(missing)} required artifact(s): {missing}")
        if extra:
            parts.append(f"EXTRA {len(extra)} artifact(s) that are not CBS inputs: "
                         f"{extra}")
        raise ArtifactSetError(
            f"{where} must cover EXACTLY the {N_REQUIRED_ARTIFACTS} CBS required "
            f"artifacts, no subset and no superset. " + "; ".join(parts) + ". "
            f"A subset means a run's identity omits inputs it actually consumed; a "
            f"superset means the identity silently widens to cover a file no "
            f"reviewer agreed was an input, so two runs over the same five inputs "
            f"would get different identities. Required set: "
            f"{sorted(CBS_REQUIRED_ARTIFACTS)}")
    return tuple(CBS_REQUIRED_ARTIFACTS)


# --------------------------------------------------------------------------
# bound convention
# --------------------------------------------------------------------------

def _recompute_bound(path: Path, date_col: str = "game_date"):
    """`bound_from_dates` over an artifact's own game dates, or a reason it failed."""
    try:
        col = pd.read_parquet(path, columns=[date_col])[date_col]
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    dates = pd.to_datetime(col, errors="coerce").dropna()
    if dates.empty:
        return None, f"no parseable {date_col} values"
    try:
        return aoi.bound_from_dates(dates.tolist()), None
    except Exception as exc:                                  # pragma: no cover
        return None, f"{type(exc).__name__}: {exc}"


def bound_convention_status(root: Path | str = REPO_ROOT) -> dict:
    """Does every required artifact's bound follow the convention it declares?

    For a date-bearing artifact the declared `fit_through_date` is compared with
    `bound_from_dates(game_date)` recomputed from the bytes on disk:

    * equal            -> `follows_convention`
    * declared LATER   -> `conservative_but_not_exact` — over-cautious, reported
      and NOT a blocker, because a bound that is too late is never wrong in the
      unsafe direction
    * declared EARLIER -> `anti_conservative` — a HARD blocker. This is exactly
      the midnight reading of `max(game_date)`, which sits before the games
      played on that date, and is the failure `bound_from_dates` exists to
      prevent.

    `contract.json` has no dates of its own; its bound is inherited and is checked
    against the maximum of the date-bearing bounds.
    """
    root = Path(root)
    out: dict[str, dict] = {}
    recomputed: dict[str, object] = {}

    for rel in DATE_BEARING_ARTIFACTS:
        p = root / rel
        rec = {"exists": p.exists(), "kind": "date_bearing",
               "convention": BOUND_CONVENTION, "declared": None,
               "recomputed": None, "declared_bound_source": None,
               "verdict": None, "problem": None}
        if not p.exists():
            rec["verdict"], rec["problem"] = "unknown", "artifact absent"
            out[rel] = rec
            continue
        try:
            m = aoi.read_manifest(p)
        except Exception as exc:
            rec["verdict"] = "unknown"
            rec["problem"] = f"unreadable manifest: {type(exc).__name__}: {exc}"
            out[rel] = rec
            continue
        rec["declared_bound_source"] = m.get("bound_source")
        declared = aoi.to_utc(m["fit_through_date"])
        rec["declared"] = declared.isoformat()
        bound, why = _recompute_bound(p)
        if bound is None:
            rec["verdict"], rec["problem"] = "unknown", why
            out[rel] = rec
            continue
        recomputed[rel] = bound
        rec["recomputed"] = bound.isoformat()
        if declared == bound:
            rec["verdict"] = "follows_convention"
        elif declared > bound:
            rec["verdict"] = "conservative_but_not_exact"
            rec["problem"] = ("declared bound is LATER than bound_from_dates; "
                              "over-cautious, so not a blocker")
        else:
            rec["verdict"] = "anti_conservative"
            rec["problem"] = (
                f"declared {declared.isoformat()} is EARLIER than the convention's "
                f"{bound.isoformat()}. A bare game_date read as midnight sits BEFORE "
                f"the games played on that date, so an as-of check against a forecast "
                f"committed that day would pass while the artifact already contained "
                f"that evening's result")
        out[rel] = rec

    inherited_from = max(recomputed.values()) if recomputed else None
    for rel in INHERITED_BOUND_ARTIFACTS:
        p = root / rel
        rec = {"exists": p.exists(), "kind": "inherited",
               "convention": f"max over {list(DATE_BEARING_ARTIFACTS)} via "
                             f"{BOUND_CONVENTION}",
               "declared": None, "recomputed": None,
               "declared_bound_source": None, "verdict": None, "problem": None}
        if not p.exists():
            rec["verdict"], rec["problem"] = "unknown", "artifact absent"
            out[rel] = rec
            continue
        try:
            m = aoi.read_manifest(p)
        except Exception as exc:
            rec["verdict"] = "unknown"
            rec["problem"] = f"unreadable manifest: {type(exc).__name__}: {exc}"
            out[rel] = rec
            continue
        rec["declared_bound_source"] = m.get("bound_source")
        declared = aoi.to_utc(m["fit_through_date"])
        rec["declared"] = declared.isoformat()
        if inherited_from is None:
            rec["verdict"] = "unknown"
            rec["problem"] = "no date-bearing bound could be recomputed to inherit from"
        else:
            rec["recomputed"] = inherited_from.isoformat()
            if declared == inherited_from:
                rec["verdict"] = "follows_convention"
            elif declared > inherited_from:
                rec["verdict"] = "conservative_but_not_exact"
                rec["problem"] = "inherited bound is later than the tables it describes"
            else:
                rec["verdict"] = "anti_conservative"
                rec["problem"] = (
                    f"declared {declared.isoformat()} is EARLIER than the maximum "
                    f"bound of the tables it describes ({inherited_from.isoformat()})")
        out[rel] = rec
    return out


def bound_convention_blockers(status: dict) -> list[dict]:
    """The `anti_conservative` verdicts, as hard blockers."""
    return [{"kind": "bound_convention_violation", "artifact": rel,
             "repairable": True, "detail": e["problem"]}
            for rel, e in sorted(status.items())
            if e.get("verdict") == "anti_conservative"]


def correct_bound_to_convention(rel: str, *, root: Path | str = REPO_ROOT,
                                append_note: str, date_col: str = "game_date",
                                dry_run: bool = True) -> dict:
    """Rewrite ONE sidecar's bound to `bound_from_dates`, preserving everything else.

    `dry_run=True` by default: rewriting an attestation is a provenance claim, not
    a chore. Producer, `fit_seasons`, `asof_granularity` and every extra key the
    existing manifest carries are preserved verbatim; the existing `notes` are
    preserved and `append_note` is APPENDED, so the record says what changed and
    why rather than quietly showing a different number than it did yesterday.
    """
    root = Path(root)
    p = root / rel
    if not p.exists():
        raise ProvenancePreconditionError(f"cannot re-attest an absent artifact: {rel}")
    old = aoi.read_manifest(p)
    bound, why = _recompute_bound(p, date_col)
    if bound is None:
        raise BoundConventionError(f"{rel}: cannot recompute the bound: {why}")

    reserved = {"schema", "artifact", "producer", "fit_through_date",
                "fit_through_season", "fit_seasons", "asof_granularity",
                "content_sha256", "content_bytes", "created_at", "notes",
                "fit_through_by_season"}
    extra = {k: v for k, v in old.items() if k not in reserved}
    extra.setdefault("bound_source", f"game_date via {BOUND_CONVENTION}")
    extra["attested_by"] = PROVENANCE_ID

    notes = str(old.get("notes", "")).rstrip()
    notes = f"{notes} {append_note.strip()}".strip()

    plan = {"artifact": rel, "old_fit_through_date": old["fit_through_date"],
            "new_fit_through_date": bound.isoformat(),
            "changed": old["fit_through_date"] != bound.isoformat(),
            "producer_preserved": old["producer"],
            "extra_keys_preserved": sorted(extra),
            "notes_preserved_and_appended": True, "dry_run": dry_run}
    if dry_run:
        plan["note"] = "dry run: no manifest was written"
        return plan
    written = aoi.write_manifest(
        p, producer=old["producer"], fit_through_date=bound,
        fit_through_season=int(old["fit_through_season"]),
        fit_seasons=list(old.get("fit_seasons") or [old["fit_through_season"]]),
        asof_granularity=old.get("asof_granularity", "artifact"),
        fit_through_by_season=old.get("fit_through_by_season"),
        notes=notes, extra=extra)
    plan["manifest_path"] = str(written)
    plan["note"] = "manifest rewritten; content_sha256 recomputed from the bytes"
    return plan


# --------------------------------------------------------------------------
# the audit
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# v3-keyed base audit (reconciled at fan-in)
# --------------------------------------------------------------------------

#: `/2`'s required-column contract, re-keyed onto the v3 contract paths. The
#: column requirements themselves are unchanged: v3 changed which ROWS are
#: obligations, not which columns an obligation carries.
REQUIRED_COLUMNS_V3 = {
    PLAYER_GAME_V3: _p2.REQUIRED_COLUMNS[_p2.PLAYER_GAME],
    TEAM_GAME_V3: _p2.REQUIRED_COLUMNS[_p2.TEAM_GAME],
    _p2.MASTER_PLAYER: _p2.REQUIRED_COLUMNS[_p2.MASTER_PLAYER],
    _p2.MASTER_TEAM: _p2.REQUIRED_COLUMNS[_p2.MASTER_TEAM],
}


def schema_status_v3(root: Path | str = REPO_ROOT) -> dict:
    """Do the v3 artifacts supply EVERY required column? ALL, not any."""
    root = Path(root)
    out = {}
    for rel, required in REQUIRED_COLUMNS_V3.items():
        path = root / rel
        if not path.exists():
            out[rel] = {"exists": False, "complete": False,
                        "missing": list(required), "present": []}
            continue
        try:
            cols = set(pd.read_parquet(path).columns)
        except Exception as exc:
            out[rel] = {"exists": True, "complete": False, "unreadable": True,
                        "problem": f"{type(exc).__name__}: {exc}",
                        "missing": list(required), "present": []}
            continue
        missing = [c for c in required if c not in cols]
        out[rel] = {"exists": True, "complete": not missing,
                    "n_required": len(required),
                    "n_present": len(required) - len(missing),
                    "missing": missing,
                    "present": [c for c in required if c in cols]}
    return out


def _base_audit_v3(root: Path) -> dict:
    """`/2`'s audit shape, computed over the v3 artifact set.

    `_p2.audit` is keyed to v2's paths and v2's `MUST_BE_ATTESTED`, so delegating
    to it wholesale would have audited the superseded universe while this module
    enforced the new one.
    """
    att = _p2.attestation_status(root, CBS_REQUIRED_ARTIFACTS)
    for entry in att.values():
        entry["must_be_attested"] = True      # all five are required under v10
    sch = schema_status_v3(root)

    hard = []
    for rel, e in sorted(att.items()):
        if not e["exists"]:
            hard.append({"kind": "artifact_absent", "artifact": rel,
                         "repairable": True, "detail": "file not found"})
        elif not e["manifest_valid"]:
            hard.append({"kind": "artifact_unattested", "artifact": rel,
                         "repairable": True, "detail": e["problem"]})
        elif e["hash_ok"] is False:
            hard.append({"kind": "artifact_hash_drift", "artifact": rel,
                         "repairable": True,
                         "detail": "manifest does not match the bytes on disk"})
    for rel, e in sorted(sch.items()):
        if e["exists"] and not e["complete"]:
            hard.append({"kind": "required_columns_missing", "artifact": rel,
                         "repairable": True, "detail": f"missing {e['missing']}"})

    return {"attestation": att, "required_columns": sch,
            "contract_feature_availability": _p2.feature_availability(root),
            "hard_blockers": hard, "n_hard_blockers": len(hard),
            "accepted_policy_limitations": ACCEPTED_POLICY_LIMITATIONS,
            "n_accepted_policy_limitations": len(ACCEPTED_POLICY_LIMITATIONS)}


def audit(root: Path | str = REPO_ROOT) -> dict:
    """`/2`'s audit, plus the bound-convention check and the exact-set verdict.

    Schema, provenance and identity only. Fits nothing, predicts nothing, scores
    nothing, relates no feature to any outcome.
    """
    root = Path(root)
    base = _base_audit_v3(root)
    bounds = bound_convention_status(root)
    hard = list(base["hard_blockers"]) + bound_convention_blockers(bounds)

    try:
        require_exact_artifact_set(CBS_REQUIRED_ARTIFACTS)
        set_ok, set_problem = True, None
    except ArtifactSetError as exc:                            # pragma: no cover
        set_ok, set_problem = False, str(exc)

    out = dict(base)
    out.update({
        "schema": AUDIT_SCHEMA,
        "provenance": PROVENANCE_ID,
        "supersedes": SUPERSEDES,
        "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "required_artifact_set": list(CBS_REQUIRED_ARTIFACTS),
        "n_required_artifacts": N_REQUIRED_ARTIFACTS,
        "artifact_set_rule": ("EXACT key equality with CBS_REQUIRED_ARTIFACTS: "
                              "subsets and supersets are both rejected"),
        "artifact_set_self_check": {"ok": set_ok, "problem": set_problem},
        "bound_convention": BOUND_CONVENTION,
        "bound_convention_status": bounds,
        "hard_blockers": hard,
        "n_hard_blockers": len(hard),
        # still NOT `real_run_permitted`; see /2's reasoning, which stands
        "provenance_preconditions_met": not hard,
        "supervisory_authorization_required": True,
        "verdict": ("all hard blockers cleared; the accepted policy limitations "
                    "above are carried and labelled per row. This is a statement "
                    "about provenance readiness ONLY — it is not authorization to "
                    "fit, predict, score or evaluate anything."
                    if not hard else
                    f"{len(hard)} hard blocker(s) must be fixed before a real run"),
    })
    return out


# --------------------------------------------------------------------------
# manifest construction
# --------------------------------------------------------------------------

def _manifest_body(status: dict, artifacts: tuple, frames: dict) -> dict:
    return {
        "schema": SNAPSHOT_MANIFEST_SCHEMA,
        "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
        "frame_identity_mode": REAL_PATH_MODE,
        "provenance": PROVENANCE_ID,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifact_set_rule": ("EXACT key equality with CBS_REQUIRED_ARTIFACTS: "
                              "subsets and supersets are both rejected"),
        "n_required_artifacts": N_REQUIRED_ARTIFACTS,
        "artifacts": {rel: {"sha256": status[rel]["sha256"],
                            "bytes": status[rel]["bytes"]}
                      for rel in sorted(artifacts)},
        "frames": frames_digest(frames, mode=REAL_PATH_MODE),
        "accepted_policy_limitations": ACCEPTED_POLICY_LIMITATIONS,
    }


def build_snapshot_manifest(frames: dict, *, root: Path | str = REPO_ROOT,
                            require_attested: bool = True,
                            synthetic: bool = False,
                            _test_artifacts=None) -> dict:
    """A snapshot manifest over EXACTLY the five required artifacts.

    `/2` took `artifacts=` as an ordinary default, so a caller could build a valid
    one-artifact manifest and `cbs_v9.snapshot_identity` would accept it. Here the
    set is not a parameter of the real path at all: it is fixed, and equality with
    `CBS_REQUIRED_ARTIFACTS` is enforced in both directions.

    `_test_artifacts` is the synthetic-only escape. It is keyword-only, it is
    underscore-prefixed, it is REJECTED OUTRIGHT unless `synthetic=True` is also
    passed explicitly, and `synthetic=True` on its own grants nothing — the exact
    five still apply. See the module docstring for why a real run cannot reach it;
    real callers should use `build_real_snapshot_manifest`, which has no artifact
    parameter to misuse.
    """
    root = Path(root)

    if _test_artifacts is not None and not synthetic:
        raise TestEscapeMisuse(
            "_test_artifacts is a SYNTHETIC-ONLY override and was passed without "
            "synthetic=True. It is refused outright rather than being ignored or "
            "falling back to the required five: silently ignoring it would let a "
            "caller believe they had overridden the artifact set, and silently "
            "honouring it would let one stray keyword disable the check that "
            "exists to guarantee a real run names every input it consumed. Two "
            "independent explicit tokens are required, by design.")

    if _test_artifacts is None:
        # the real path AND a synthetic run that did not ask for an override:
        # both get the exact five
        artifacts = require_exact_artifact_set(
            CBS_REQUIRED_ARTIFACTS, where="snapshot manifest")
        test_only = False
    else:
        artifacts = tuple(_test_artifacts)
        if not artifacts:
            raise TestEscapeMisuse("_test_artifacts must name at least one artifact")
        test_only = True

    status = attestation_status(root, artifacts)
    problems = []
    for rel, e in sorted(status.items()):
        if not e["exists"]:
            problems.append(f"{rel}: absent")
        elif e["must_be_attested"] and require_attested:
            if not e["manifest_valid"]:
                problems.append(f"{rel}: unattested ({e['problem']})")
            elif e["hash_ok"] is False:
                problems.append(f"{rel}: manifest does not match the file's bytes")
    if problems:
        raise ProvenancePreconditionError(
            "cannot build a snapshot manifest; required inputs are not "
            "provenance-ready: " + "; ".join(problems))

    man = _manifest_body(status, artifacts, frames)
    if test_only:
        # the escape LABELS its own output, so the refusal downstream does not
        # depend on anyone remembering how this manifest was made
        man["synthetic"] = True
        man["real_path_permitted"] = False
        man["artifact_set_scope"] = "TEST_ONLY_SYNTHETIC_OVERRIDE"
        man["why_not_real"] = (
            "built through the synthetic-only _test_artifacts escape; its artifact "
            "set is NOT the five CBS required inputs and it is refused by "
            "require_real_snapshot_manifest")
    else:
        man["synthetic"] = bool(synthetic)
        man["real_path_permitted"] = not synthetic
    return man


def build_real_snapshot_manifest(frames: dict, *,
                                 root: Path | str = REPO_ROOT) -> dict:
    """The REAL entry point. No artifact parameter exists, so none can be misused.

    This function deliberately accepts no `artifacts`, no `_test_artifacts`, no
    `synthetic` and no `**kwargs`. A real-path caller therefore has no argument
    through which the artifact set could be narrowed, widened or overridden — the
    escape is not merely discouraged here, it is unreachable.
    """
    return build_snapshot_manifest(frames, root=root, require_attested=True)


def require_real_snapshot_manifest(manifest: dict) -> dict:
    """Refuse any manifest a real run must not consume. Raises, or returns a receipt.

    Checked independently of how the manifest was built, so a manifest that took
    the synthetic escape cannot be laundered into a real run by passing it along.
    """
    if not isinstance(manifest, dict):
        raise ArtifactSetError("snapshot manifest must be a mapping")
    if manifest.get("real_path_permitted") is False or manifest.get("synthetic"):
        raise ArtifactSetError(
            f"this manifest is stamped synthetic / real_path_permitted=False "
            f"({manifest.get('why_not_real') or 'built for a synthetic fixture'}) "
            f"and must not be consumed by a real run")
    if manifest.get("frame_identity_schema") != FRAME_IDENTITY_SCHEMA:
        raise ArtifactSetError(
            f"manifest must declare frame_identity_schema {FRAME_IDENTITY_SCHEMA!r}; "
            f"got {manifest.get('frame_identity_schema')!r}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ArtifactSetError("snapshot manifest lists no artifacts")
    require_exact_artifact_set(artifacts.keys(), where="snapshot manifest")
    frames = manifest.get("frames")
    if not isinstance(frames, dict) or not frames:
        raise ArtifactSetError(
            "snapshot manifest declares no frames; the identity must cover the "
            "frames actually consumed, not only the files they came from")
    return {"receipt": "real_snapshot_manifest/1", "ok": True,
            "provenance": PROVENANCE_ID,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "n_artifacts": len(artifacts), "n_frames": len(frames)}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rep = audit(args.root)
    text = json.dumps(rep, indent=2, default=str) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"\nhard blockers: {rep['n_hard_blockers']}  |  "
          f"carried policy limitations: {rep['n_accepted_policy_limitations']}")
    for rel, e in sorted(rep["bound_convention_status"].items()):
        print(f"  bound  {e['verdict']:28s}  {rel}")
    print(rep["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
