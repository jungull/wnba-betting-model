#!/usr/bin/env python3
"""cbs_provenance.py — `cbs_provenance/2`, the corrected attestation and audit layer.

`cbs_real_adapter.py` is part of v8's registered implementation set and is left
byte-untouched. This module supersedes its audit half and fixes three things it
got wrong.

1. **`MUST_BE_ATTESTED` covered three of five consumed artifacts.** v8 claimed
   that "every required artifact blocks manifest construction" while omitting
   `team_game.parquet` and `contract.json`. The claim was broader than the code.
   Here **all five** must be attested, and the list that is enforced is the same
   list that is documented.

2. **Availability verdicts used `bool(any present)`.** `bool(["minutes"])` is
   True, so a frame supplying **one** of fourteen registered features would have
   reported the feature set as available. Every verdict now requires **all**
   registered fields, and names precisely which are missing.

3. **Accepted policy limitations were labelled as blockers.** v8 emitted a flat
   `blocking` list mixing conditions that can be repaired (an unattested
   artifact, a missing column) with one that never can: **no observed historical
   feature-source or outcome-availability timestamp exists, and none can be
   created retrospectively.** That second kind is not a defect awaiting a fix. It
   is a disclosed limitation handled by the approved conservative policy, and
   filing it under "blocking" implies a repair that would have to be fabricated.

The two are now reported separately, because the correct response differs: a hard
blocker must be **fixed** before a real run; a policy limitation must be
**disclosed and carried**.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import asof_invariant as aoi
from cbs_frame_identity import FRAME_IDENTITY_SCHEMA, frames_digest
from cbs_v5 import P_ACTIVE_FEATURES, REQUIRED_CHANNELS
from cbs_v9 import SNAPSHOT_MANIFEST_SCHEMA

PROVENANCE_ID = "cbs_provenance/2"
AUDIT_SCHEMA = "cbs_real_input_audit/2"

REPO_ROOT = Path(__file__).resolve().parent
CONTRACT_DIR = "experiments/prediction_contract_v2"

PLAYER_GAME = f"{CONTRACT_DIR}/player_game.parquet"
TEAM_GAME = f"{CONTRACT_DIR}/team_game.parquet"
CONTRACT_JSON = f"{CONTRACT_DIR}/contract.json"
MASTER_PLAYER = "data/masters/master_player.parquet"
MASTER_TEAM = "data/masters/master_team.parquet"

#: Every artifact a real CBS run consumes. All five are enforced; the list that
#: is checked IS the list that is documented.
CBS_REQUIRED_ARTIFACTS = (PLAYER_GAME, TEAM_GAME, CONTRACT_JSON,
                          MASTER_PLAYER, MASTER_TEAM)
MUST_BE_ATTESTED = CBS_REQUIRED_ARTIFACTS

#: Columns each artifact must supply, in full. ALL of them, not any of them.
REQUIRED_COLUMNS = {
    PLAYER_GAME: ("row_uid", "game_id", "player_id", "team_id", "season",
                  "game_date", "forecast_cutoff", "fold_id", "appeared",
                  "minutes", "pts", "fga"),
    TEAM_GAME: ("row_uid", "game_id", "team_id", "season", "game_date",
                "forecast_cutoff", "fold_id"),
    MASTER_PLAYER: ("player_id", "team_id", "game_id", "season", "game_date",
                    "minutes", "starter_flag", "dnp_reason", "is_home"),
    MASTER_TEAM: ("game_id", "team_id", "season", "game_date", "is_home",
                  "pts", "ftm", "fgm", "fg3m", "points_paint"),
}

#: The two Stage-A features the RUNNER derives from its own admitted history.
#: The adapter is not expected to supply them, so requiring them here would
#: manufacture a permanent false negative.
RUNNER_DERIVED_FEATURES = ("p_plays_prior", "player_gp_season")
ADAPTER_DERIVED_FEATURES = tuple(f for f in P_ACTIVE_FEATURES
                                 if f not in RUNNER_DERIVED_FEATURES)

#: Limitations that are DISCLOSED AND CARRIED, not repaired. No amount of work on
#: this repository can retrospectively create an observation that was never made.
ACCEPTED_POLICY_LIMITATIONS = {
    "observed_feature_source_timestamp": {
        "observed_available": False,
        "handled_by": "conservative policy bound, labelled `policy` on every row",
        "policy_equals": "asof_invariant.bound_from_dates",
        "repairable_retrospectively": False,
        "why": ("no per-row source read time was recorded for the Stage-A history "
                "at the time; master observed_time is a local file mtime with ~10 "
                "distinct values and records when this machine wrote the file"),
    },
    "observed_outcome_availability_timestamp": {
        "observed_available": False,
        "handled_by": ("the registered +36h conservative policy, identical to "
                       "asof_invariant.bound_from_dates, labelled `policy` per row"),
        "repairable_retrospectively": False,
        "why": ("nothing in this repository records when a final box score became "
                "observable; a value invented now would be a fabricated timestamp"),
    },
}


class ProvenancePreconditionError(RuntimeError):
    """A real input is absent, unattested, incomplete, or fails its content hash."""


def artifact_sha256(path: Path) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


# --------------------------------------------------------------------------
# attestation over ALL FIVE artifacts
# --------------------------------------------------------------------------

def attestation_status(root: Path | str = REPO_ROOT,
                       artifacts=CBS_REQUIRED_ARTIFACTS) -> dict:
    """Existence, manifest validity and content-hash agreement, per artifact."""
    root = Path(root)
    out = {}
    for rel in artifacts:
        p = root / rel
        entry = {"exists": p.exists(), "must_be_attested": rel in MUST_BE_ATTESTED,
                 "has_manifest": False, "manifest_valid": False, "hash_ok": None,
                 "fit_through_date": None, "producer": None, "problem": None}
        if not p.exists():
            entry["problem"] = "artifact absent"
            out[rel] = entry
            continue
        digest, size = artifact_sha256(p)
        entry["sha256"], entry["bytes"] = digest, size
        mpath = Path(str(p) + aoi.MANIFEST_SUFFIX)
        entry["has_manifest"] = mpath.exists()
        if not mpath.exists():
            entry["problem"] = "no asof_invariant manifest sidecar"
            out[rel] = entry
            continue
        try:
            m = aoi.read_manifest(p)
            entry["manifest_valid"] = True
            entry["fit_through_date"] = str(m.get("fit_through_date"))
            entry["producer"] = m.get("producer")
            entry["asof_granularity"] = m.get("asof_granularity")
            entry["hash_ok"] = (str(m.get("content_sha256")) == digest)
            if not entry["hash_ok"]:
                entry["problem"] = ("manifest content_sha256 does not match the file; "
                                    "the artifact was rebuilt without updating it")
        except Exception as exc:
            entry["problem"] = f"{type(exc).__name__}: {exc}"
        out[rel] = entry
    return out


def schema_status(root: Path | str = REPO_ROOT) -> dict:
    """Do the artifacts supply **every** required column? ALL, not any."""
    root = Path(root)
    out = {}
    for rel, required in REQUIRED_COLUMNS.items():
        p = root / rel
        if not p.exists():
            out[rel] = {"exists": False, "complete": False,
                        "missing": list(required), "present": []}
            continue
        try:
            cols = set(pd.read_parquet(p).columns)
        except Exception as exc:
            # An artifact that cannot be opened is a reported blocker, not a
            # traceback. A corrupt file must not be able to crash the audit that
            # exists to notice it.
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


def feature_availability(root: Path | str = REPO_ROOT) -> dict:
    """Which Stage-A features and team channels the CONTRACT itself supplies.

    Reported with an explicit `complete` flag computed over the FULL registered
    set. v8 returned `bool(list_of_present)`, which is True as soon as a single
    field appears — so a frame supplying one of fourteen features would have been
    reported as supplying the feature set.
    """
    root = Path(root)
    out = {}
    pg = root / PLAYER_GAME
    if pg.exists():
        try:
            cols = set(pd.read_parquet(pg).columns)
        except Exception:
            cols = set()
        present = [f for f in ADAPTER_DERIVED_FEATURES if f in cols]
        missing = [f for f in ADAPTER_DERIVED_FEATURES if f not in cols]
        out["stage_a_from_contract"] = {
            "n_required": len(ADAPTER_DERIVED_FEATURES),
            "n_present": len(present), "present": present, "missing": missing,
            "complete": not missing,
            "note": ("p_plays_prior and player_gp_season are derived by the RUNNER "
                     "from its own admitted history and are excluded from this set")}
    tg = root / TEAM_GAME
    if tg.exists():
        try:
            cols = set(pd.read_parquet(tg).columns)
        except Exception:
            cols = set()
        req = [f"ch_{c}" for c in REQUIRED_CHANNELS] + ["side", "team_points"]
        present = [c for c in req if c in cols]
        missing = [c for c in req if c not in cols]
        out["team_inputs_from_contract"] = {
            "n_required": len(req), "n_present": len(present),
            "present": present, "missing": missing, "complete": not missing}
    return out


# --------------------------------------------------------------------------
# the audit: hard blockers separated from carried policy limitations
# --------------------------------------------------------------------------

def audit(root: Path | str = REPO_ROOT) -> dict:
    """Schema, provenance and identity only. Fits nothing, predicts nothing.

    Every field is a column name, a byte count, a hash, a count or a boolean. No
    outcome is summarised beyond presence, no feature is related to any target,
    and nothing is scored.
    """
    root = Path(root)
    att = attestation_status(root)
    sch = schema_status(root)
    feat = feature_availability(root)

    hard: list[dict] = []
    for rel, e in sorted(att.items()):
        if not e["exists"]:
            hard.append({"kind": "artifact_absent", "artifact": rel,
                         "repairable": True, "detail": "file not found"})
        elif e["must_be_attested"] and not e["manifest_valid"]:
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

    return {
        "schema": AUDIT_SCHEMA, "provenance": PROVENANCE_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": ("schema, provenance and identity only: no fitting, no prediction, "
                  "no model coverage or accuracy figure, no scoring, no "
                  "profitability evaluation, no feature-outcome relationship"),
        "attestation": att,
        "required_columns": sch,
        "contract_feature_availability": feat,
        "hard_blockers": hard,
        "n_hard_blockers": len(hard),
        "accepted_policy_limitations": ACCEPTED_POLICY_LIMITATIONS,
        "n_accepted_policy_limitations": len(ACCEPTED_POLICY_LIMITATIONS),
        "policy_limitations_are_not_blockers": (
            "these are disclosed and carried, not repaired: no observation that was "
            "never made can be created retrospectively, and a value invented now "
            "would be a fabricated timestamp"),
        # Deliberately NOT called `real_run_permitted`. Clearing these checks means
        # the provenance preconditions hold; it is not permission to run. That
        # remains a supervisory decision, and a field named "permitted" would
        # outrun the evidence the moment attestation landed.
        "provenance_preconditions_met": not hard,
        "supervisory_authorization_required": True,
        "verdict": ("all hard blockers cleared; the accepted policy limitations "
                    "above are carried and labelled per row. This is a statement "
                    "about provenance readiness ONLY — it is not authorization to "
                    "fit, predict, score or evaluate anything."
                    if not hard else
                    f"{len(hard)} hard blocker(s) must be fixed before a real run"),
    }


# --------------------------------------------------------------------------
# attestation actions and manifest construction
# --------------------------------------------------------------------------

def attest_artifact(rel: str, *, root: Path | str = REPO_ROOT, producer: str,
                    date_col: str = "game_date", season_col: str = "season",
                    dates=None, seasons=None, granularity: str = "row",
                    dry_run: bool = True) -> dict:
    """Write an `asof_invariant/1` manifest, bound to GAME DATES.

    `dry_run=True` by default: attesting an artifact is a provenance claim, not a
    chore. The bound comes from `bound_from_dates` over game dates — never from
    `observed_time`, which is a local file mtime — and the manifest notes say so,
    so a later reader cannot mistake which was used.
    """
    root = Path(root)
    p = root / rel
    if not p.exists():
        raise ProvenancePreconditionError(f"cannot attest an absent artifact: {rel}")

    if dates is None or seasons is None:
        df = pd.read_parquet(p, columns=[date_col, season_col])
        dates = pd.to_datetime(df[date_col], errors="coerce")
        if dates.isna().any():
            raise ProvenancePreconditionError(
                f"{rel}: {int(dates.isna().sum())} unparseable {date_col} values")
        dates = dates.tolist()
        seasons = sorted(int(s) for s in pd.unique(df[season_col]))

    bound = aoi.bound_from_dates(dates)
    plan = {"artifact": rel, "producer": producer,
            "fit_through_date": bound.isoformat(),
            "fit_through_season": max(seasons), "fit_seasons": list(seasons),
            "asof_granularity": granularity,
            "bound_source": "game_date via asof_invariant.bound_from_dates",
            "observed_time_deliberately_unused": True, "dry_run": dry_run}
    if dry_run:
        plan["note"] = "dry run: no manifest was written"
        return plan
    written = aoi.write_manifest(
        p, producer=producer, fit_through_date=bound,
        fit_through_season=max(seasons), fit_seasons=list(seasons),
        asof_granularity=granularity,
        notes=("As-of bound derived from game dates via bound_from_dates. Any "
               "observed_time column in this artifact is a LOCAL FILE MTIME and is "
               "deliberately NOT used as an as-of bound."),
        extra={"attested_by": PROVENANCE_ID,
               "bound_source": "game_date via asof_invariant.bound_from_dates"})
    plan["manifest_path"] = str(written)
    plan["note"] = "manifest written"
    return plan


def build_snapshot_manifest(frames: dict, *, root: Path | str = REPO_ROOT,
                            artifacts=CBS_REQUIRED_ARTIFACTS,
                            require_attested: bool = True) -> dict:
    """A `cbs_snapshot_manifest/3` over verified artifact bytes and frame digests.

    Refuses while ANY of the five required artifacts is unattested — the check
    now matches the claim.
    """
    root = Path(root)
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

    return {
        "schema": SNAPSHOT_MANIFEST_SCHEMA,
        "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
        "provenance": PROVENANCE_ID,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifacts": {rel: {"sha256": status[rel]["sha256"],
                            "bytes": status[rel]["bytes"]}
                      for rel in sorted(status) if status[rel]["exists"]},
        "frames": frames_digest(frames),
        "accepted_policy_limitations": ACCEPTED_POLICY_LIMITATIONS,
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
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
    print(rep["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
