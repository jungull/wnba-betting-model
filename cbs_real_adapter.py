#!/usr/bin/env python3
"""cbs_real_adapter.py — the provenance layer between the real artifacts and the arm.

`contract_baseline_suite_v8` will not accept a frame whose feature sources cannot
be shown to precede its cutoff, whose artifacts do not match their bytes on disk,
or whose identity is not bound to the frames actually consumed. Something has to
*produce* those things from the real files. This module is that something, and it
is versioned so a later reader can tell which construction produced a given run.

**IT DOES NOT FIT, PREDICT OR SCORE.** There is no model here, no coefficient, no
accuracy figure, no coverage figure, and nothing that relates a feature to an
outcome. It reads schemas and bytes, labels provenance, counts, and hashes.

WHAT IT IS FOR
--------------
The real inputs are not ready, and the honest response is to make that
machine-checkable rather than to write it down and hope. Concretely:

* `experiments/prediction_contract_v2/player_game.parquet` holds **none** of the
  14 Stage-A features; `team_game.parquet` holds **no** `ch_*`, no `side`, no
  `team_points`. All of them have to come from `data/masters/`.
* **`data/masters/*.parquet` are unattested.** Neither has a `.manifest.json`, and
  no entry in `asof_invariant.FITTED_ARTIFACT_GLOBS` matches them, so
  `--scan` cannot even report them as missing. An arm fed by an artifact nothing
  attests has a provenance chain with a hole in the middle.
* **`observed_time` in both masters is a build-time stamp**, not an observation of
  anything: it takes ten distinct values across 33,712 player rows, all inside the
  last two local refresh runs, and it is a file mtime by construction
  (`build_masters.py`). It must never be used as an as-of bound. `attest_master`
  therefore derives the bound from `game_date` through
  `asof_invariant.bound_from_dates`, and records in the manifest that it did.
* No observed per-row feature-source timestamp, and no observed
  outcome-availability timestamp, exists anywhere in this repository. Every source
  this adapter emits is therefore labelled **`policy`**, and the label travels
  with the data rather than living in a document.

FAIL-CLOSED, DELIBERATELY
-------------------------
`build_snapshot_manifest` refuses to describe an artifact that is not attested.
That is the point: it converts "the masters are unattested" from a sentence in a
report into a condition that stops a run. Attesting them is a separate, explicit
act (`attest_master`), so nobody closes the gap by accident.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import asof_invariant as aoi
from cbs_v8 import (REQUIRED_PLAYER_FEATURE_SOURCES, REQUIRED_TEAM_FEATURE_SOURCES,
                    SNAPSHOT_MANIFEST_SCHEMA, frame_digest)

ADAPTER_ID = "cbs_real_adapter/1"
SOURCE_LABEL_SCHEMA = "cbs_source_labels/1"

REPO_ROOT = Path(__file__).resolve().parent

#: The real artifacts an arm run consumes. Every one is hashed by bytes.
CONTRACT_DIR = "experiments/prediction_contract_v2"
REQUIRED_ARTIFACTS = (
    f"{CONTRACT_DIR}/player_game.parquet",
    f"{CONTRACT_DIR}/team_game.parquet",
    f"{CONTRACT_DIR}/contract.json",
    "data/masters/master_player.parquet",
    "data/masters/master_team.parquet",
)

#: Artifacts that MUST carry an `asof_invariant/1` manifest before a real run.
MUST_BE_ATTESTED = (
    f"{CONTRACT_DIR}/player_game.parquet",
    "data/masters/master_player.parquet",
    "data/masters/master_team.parquet",
)

#: Every source this adapter can currently emit, and what backs it. There is no
#: `observed` entry because no observed source timestamp exists in the real data.
SOURCE_LABELS = {
    "src_asof_gamelog": {
        "label": "policy",
        "backing": "data/masters/master_player.parquet",
        "derivation": "asof_invariant.bound_from_dates over the row's own prior "
                      "game_date; a date-derived conservative bound",
        "why_not_observed": "master_player.observed_time is a local file mtime with "
                            "10 distinct values across 33,712 rows (build_masters.py); "
                            "it records when this machine wrote the file, not when the "
                            "box score was published",
    },
    "src_asof_team_gamelog": {
        "label": "policy",
        "backing": "data/masters/master_team.parquet",
        "derivation": "asof_invariant.bound_from_dates over the row's own prior "
                      "game_date",
        "why_not_observed": "master_team.observed_time is the same build-time stamp",
    },
    "src_asof_roster": {
        "label": "policy",
        "backing": f"{CONTRACT_DIR}/player_game.parquet",
        "derivation": "the contract's own candidate-at-cutoff determination, which is "
                      "a pregame roster fact fixed by the contract build",
        "why_not_observed": "the contract records no per-row roster read time",
    },
    "src_asof_schedule": {
        "label": "policy",
        "backing": f"{CONTRACT_DIR}/player_game.parquet",
        "derivation": "forecast_cutoff itself is the schedule fact; the source bound "
                      "is placed strictly before it",
        "why_not_observed": "only 10,257 of 35,615 player rows have an observed tip "
                            "(tip_time_observed_at); seasons 2021-2024 have none, so a "
                            "single uniform observed schedule source does not exist",
    },
}


class AdapterPreconditionError(RuntimeError):
    """A real input is absent, unattested, or fails its content hash."""


# --------------------------------------------------------------------------
# 1. artifact bytes and attestation
# --------------------------------------------------------------------------

def artifact_sha256(path: Path) -> tuple[str, int]:
    """(sha256 of the bytes, byte count). Streamed, so a large parquet is fine."""
    h, n = hashlib.sha256(), 0
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def attestation_status(root: Path | str = REPO_ROOT,
                       artifacts=REQUIRED_ARTIFACTS) -> dict:
    """Which required artifacts exist, and which carry a valid, current manifest.

    `hash_ok` is the clause that matters: a manifest whose `content_sha256` no
    longer matches the file is worse than no manifest, because it looks like
    provenance while describing a different artifact.
    """
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


def attest_master(rel: str, *, root: Path | str = REPO_ROOT,
                  producer: str = "build_masters.py",
                  dry_run: bool = True) -> dict:
    """Write an `asof_invariant/1` manifest for a master, bound to GAME DATES.

    Deliberately explicit and `dry_run=True` by default: attesting an artifact is
    a provenance claim, not a chore, and it should be a decision someone made
    rather than a side effect of importing this module.

    The bound comes from `bound_from_dates(game_date)` — never from
    `observed_time`, which is a local file mtime. The manifest says so in its
    notes, so a later reader cannot mistake which one was used.
    """
    root = Path(root)
    p = root / rel
    if not p.exists():
        raise AdapterPreconditionError(f"cannot attest an absent artifact: {rel}")
    df = pd.read_parquet(p, columns=["game_date", "season"])
    dates = pd.to_datetime(df["game_date"], errors="coerce")
    if dates.isna().any():
        raise AdapterPreconditionError(
            f"{rel}: {int(dates.isna().sum())} unparseable game_date values; a "
            f"date-derived as-of bound cannot be computed from them")
    seasons = sorted(int(s) for s in pd.unique(df["season"]))
    bound = aoi.bound_from_dates(dates.tolist())
    plan = {
        "artifact": rel, "producer": producer,
        "fit_through_date": bound.isoformat(),
        "fit_through_season": max(seasons), "fit_seasons": seasons,
        "asof_granularity": "row",
        "bound_source": "game_date via asof_invariant.bound_from_dates",
        "observed_time_deliberately_unused": True,
        "dry_run": dry_run,
    }
    if dry_run:
        plan["note"] = "dry run: no manifest was written"
        return plan
    written = aoi.write_manifest(
        p, producer=producer, fit_through_date=bound,
        fit_through_season=max(seasons), fit_seasons=seasons,
        asof_granularity="row",
        notes=("As-of bound derived from game_date via bound_from_dates. The "
               "observed_time column in this file is a LOCAL FILE MTIME "
               "(build_masters.py) taking ~10 distinct values, and is deliberately "
               "NOT used as an as-of bound."),
        extra={"adapter": ADAPTER_ID,
               "bound_source": "game_date via asof_invariant.bound_from_dates"})
    plan["manifest_path"] = str(written)
    plan["note"] = "manifest written"
    return plan


# --------------------------------------------------------------------------
# 2. source labelling and counts
# --------------------------------------------------------------------------

def source_label_report(sources=None) -> dict:
    """Declare, per source column, whether it is observed or policy — and why.

    v7 reported this in prose. Prose does not travel with a run receipt, and the
    single most consequential fact about this arm's provenance is that **nothing
    here is observed**. It belongs in the artifact.
    """
    sources = sources or sorted(set(REQUIRED_PLAYER_FEATURE_SOURCES)
                                | set(REQUIRED_TEAM_FEATURE_SOURCES))
    per = {s: SOURCE_LABELS[s] for s in sources if s in SOURCE_LABELS}
    unknown = [s for s in sources if s not in SOURCE_LABELS]
    labels = {s: e["label"] for s, e in per.items()}
    return {
        "schema": SOURCE_LABEL_SCHEMA, "adapter": ADAPTER_ID,
        "sources": per, "unknown_sources": unknown,
        "n_observed": sum(1 for v in labels.values() if v == "observed"),
        "n_policy": sum(1 for v in labels.values() if v == "policy"),
        "any_observed": any(v == "observed" for v in labels.values()),
        "statement": ("no observed per-row feature-source timestamp exists in this "
                      "repository; every source below is POLICY-derived and is "
                      "labelled as such on every emitted row"),
    }


def source_timestamp_counts(frame: pd.DataFrame, source_cols, *,
                            cutoff_col: str = "forecast_cutoff") -> dict:
    """Missing / unparseable / at-cutoff / late counts for one frame.

    Counting rather than raising, because this is the *audit* path: a caller
    needs the size of the problem, not just its existence. The runner is the one
    that fails closed.
    """
    out = {"n_rows": int(len(frame)), "per_source": {}, "n_missing_columns": 0,
           "n_rows_unparseable": 0, "n_rows_at_cutoff": 0, "n_rows_after_cutoff": 0}
    present = [c for c in source_cols if c in frame.columns]
    out["missing_columns"] = [c for c in source_cols if c not in frame.columns]
    out["n_missing_columns"] = len(out["missing_columns"])
    if not present or cutoff_col not in frame.columns:
        return out
    cutoff = pd.to_datetime(frame[cutoff_col], utc=True, errors="coerce")
    ts = frame[present].apply(pd.to_datetime, utc=True, errors="coerce")
    for c in present:
        out["per_source"][c] = {"n_null": int(ts[c].isna().sum())}
    out["n_rows_unparseable"] = int(ts.isna().any(axis=1).sum())
    asof = ts.max(axis=1)
    ok = asof.notna() & cutoff.notna()
    out["n_rows_at_cutoff"] = int((asof[ok] == cutoff[ok]).sum())
    out["n_rows_after_cutoff"] = int((asof[ok] > cutoff[ok]).sum())
    return out


# --------------------------------------------------------------------------
# 3. the snapshot manifest — artifacts AND frames
# --------------------------------------------------------------------------

def build_snapshot_manifest(frames: dict, *, root: Path | str = REPO_ROOT,
                            artifacts=REQUIRED_ARTIFACTS,
                            require_attested: bool = True) -> dict:
    """A `cbs_snapshot_manifest/2` naming real artifact bytes AND frame digests.

    Refuses to produce a manifest while a required artifact is unattested. This
    is what makes the unattested masters a blocker rather than a footnote: no
    manifest means no snapshot identity, and no snapshot identity means the
    runner will not start.
    """
    root = Path(root)
    status = attestation_status(root, artifacts)
    problems = []
    for rel, e in status.items():
        if not e["exists"]:
            problems.append(f"{rel}: absent")
        elif e["must_be_attested"] and require_attested:
            if not e["manifest_valid"]:
                problems.append(f"{rel}: unattested ({e['problem']})")
            elif e["hash_ok"] is False:
                problems.append(f"{rel}: manifest does not match the file's bytes")
    if problems:
        raise AdapterPreconditionError(
            "cannot build a snapshot manifest; required inputs are not provenance-"
            "ready: " + "; ".join(problems))

    return {
        "schema": SNAPSHOT_MANIFEST_SCHEMA,
        "adapter": ADAPTER_ID,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifacts": {rel: {"sha256": status[rel]["sha256"],
                            "bytes": status[rel]["bytes"]}
                      for rel in sorted(status) if status[rel]["exists"]},
        "frames": {name: frame_digest(f) for name, f in sorted(frames.items())
                   if f is not None},
        "source_labels": source_label_report(),
    }


# --------------------------------------------------------------------------
# 4. the audit entry point
# --------------------------------------------------------------------------

def audit(root: Path | str = REPO_ROOT) -> dict:
    """Schema, provenance and identity only. Fits nothing, predicts nothing.

    Everything here is a column name, a byte count, a hash, a timestamp count or
    a null count. No outcome column is summarised beyond its presence, and no
    feature is related to any target.
    """
    root = Path(root)
    report = {
        "schema": "cbs_real_input_audit/1", "adapter": ADAPTER_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": ("schema, provenance and identity only: no fitting, no prediction, "
                  "no coverage or accuracy figure, no feature-outcome relationship"),
        "attestation": attestation_status(root),
        "source_labels": source_label_report(),
    }

    from cbs_v5 import P_ACTIVE_FEATURES, REQUIRED_CHANNELS

    pg = root / CONTRACT_DIR / "player_game.parquet"
    tg = root / CONTRACT_DIR / "team_game.parquet"
    schema = {}
    if pg.exists():
        cols = set(pd.read_parquet(pg).columns)
        schema["player_game"] = {
            "n_columns": len(cols),
            "stage_a_features_present": sorted(c for c in P_ACTIVE_FEATURES if c in cols),
            "stage_a_features_absent": sorted(c for c in P_ACTIVE_FEATURES
                                              if c not in cols),
            "feature_source_columns_present": sorted(
                c for c in REQUIRED_PLAYER_FEATURE_SOURCES if c in cols),
            "has_feature_asof": "feature_asof" in cols,
            "has_outcome_observed_at": "outcome_observed_at" in cols,
        }
    if tg.exists():
        cols = set(pd.read_parquet(tg).columns)
        schema["team_game"] = {
            "n_columns": len(cols),
            "channels_present": sorted(f"ch_{c}" for c in REQUIRED_CHANNELS
                                       if f"ch_{c}" in cols),
            "channels_absent": sorted(f"ch_{c}" for c in REQUIRED_CHANNELS
                                      if f"ch_{c}" not in cols),
            "has_side": "side" in cols, "has_team_points": "team_points" in cols,
            "feature_source_columns_present": sorted(
                c for c in REQUIRED_TEAM_FEATURE_SOURCES if c in cols),
            "has_outcome_observed_at": "outcome_observed_at" in cols,
        }
    report["contract_schema"] = schema

    report["verdicts"] = {
        "stage_a_features_available_from_contract": bool(
            schema.get("player_game", {}).get("stage_a_features_present")),
        "team_channels_available_from_contract": bool(
            schema.get("team_game", {}).get("channels_present")),
        "observed_feature_asof_available": False,
        "observed_outcome_availability_available": False,
        "all_required_artifacts_attested": all(
            e["manifest_valid"] and e["hash_ok"]
            for e in report["attestation"].values() if e["must_be_attested"]),
    }
    report["blocking"] = [k for k, v in report["verdicts"].items() if not v]
    return report


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
    print(f"\nblocking: {rep['blocking']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
