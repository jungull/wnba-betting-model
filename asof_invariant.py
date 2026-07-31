"""asof_invariant.py — the as-of-date invariant for fitted artifacts.

Deliverable (C) of ``asof_invariant_audit_v1`` (experiments/registry.jsonl,
registered 2026-07-31T16:06:42Z).

WHY THIS EXISTS
---------------
``data/rapm/rapm_v0.csv`` is a STATIC player-value table fit by ``build_rapm.py``
on seasons {2021, 2022, 2023, 2024}.  Two registered experiments scored 2024 as a
TEST season while consuming it, so player values on those games were estimated
partly from the very possessions being predicted.  Nothing in the repository
could have caught that automatically: the fit window lived in a module-level
constant inside the producing script, and consumers had no machine-readable way
to ask an artifact "when does your evidence stop?".

This module supplies that missing contract.  It is deliberately dependency-free
(stdlib only) so it can be imported from a builder, a scorer, a test, or a hook
without dragging pandas into the import graph.

THE INVARIANT
-------------
    For every scored forecast row, EVERY fitted artifact feeding that row must
    prove that its latest source observation STRICTLY predates that row's
    forecast timestamp.

"Strictly" is load-bearing.  Equality is a violation, not a pass: an artifact
whose last source observation is the game being predicted is exactly the
rapm_v0 failure.  Season-level walk-forward is a coarser rule that this one
implies but does not depend on — an artifact refit for season s from seasons
< s still has to prove its last observation predates each row it scores, which
is what catches a mid-season refit that silently swept in yesterday's games.

THE MANIFEST CONVENTION
-----------------------
Every fitted artifact ``<path>`` carries a sidecar ``<path>.manifest.json``:

    {
      "schema": "asof_invariant/1",
      "artifact": "data/rapm/rapm_v0.csv",     # repo-relative
      "producer": "build_rapm.py",
      "fit_through_date": "2024-09-19T00:00:00+00:00",
      "fit_through_season": 2024,
      "fit_seasons": [2021, 2022, 2023, 2024],
      "content_sha256": "…",
      "created_at": "2026-07-31T…+00:00",
      "notes": "free text"
    }

``fit_through_date`` is the artifact's LATEST SOURCE OBSERVATION — the timestamp
of the newest datum that influenced any fitted value.  It is NOT the build time
and NOT the file mtime.  ``fit_through_season`` is the same fact at season
granularity, kept because most of this repo's leakage rules are season-shaped.
``content_sha256`` binds the manifest to the bytes it describes, so a refit that
forgets to update the manifest is detected instead of trusted.

USAGE
-----
Producer (at the end of a build)::

    import asof_invariant as aoi
    aoi.write_manifest("data/rapm/rapm_v0.csv",
                       producer="build_rapm.py",
                       fit_through_date=max_source_game_date,
                       fit_through_season=2024,
                       fit_seasons=[2021, 2022, 2023, 2024])

Consumer (before scoring anything)::

    m = aoi.read_manifest("data/rapm/rapm_v0.csv")
    aoi.assert_asof(m, forecast_time=row_forecast_time)        # per-row / per-slate
    aoi.assert_scored_seasons_clean(m, scored_seasons=[2025, 2026])

Standing check::

    python asof_invariant.py --scan --csv experiments/asof_audit/missing_manifests.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import fnmatch
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "asof_invariant/1"
MANIFEST_SUFFIX = ".manifest.json"
REPO_ROOT = Path(__file__).resolve().parent

REQUIRED_FIELDS: tuple[str, ...] = (
    "schema",
    "artifact",
    "producer",
    "fit_through_date",
    "fit_through_season",
    "content_sha256",
)

# Artifacts that carry fitted values and therefore MUST have a manifest.
# Globs are repo-relative and matched with fnmatch against posix paths.
# Keep this list conservative: a false positive costs one manifest, a false
# negative costs a retracted result.
FITTED_ARTIFACT_GLOBS: tuple[str, ...] = (
    "data/rapm/*.csv",
    "data/zone_maps/shrinkage_priors.csv",
    "data/zone_maps/player_zone_offense.csv",
    "data/zone_maps/team_zone_offense.csv",
    "data/zone_maps/team_zone_defense.csv",
    "data/zone_maps/league_zone_averages.csv",
    "experiments/channel_reval/run_summary.json",
    "experiments/channel_reval/predictions_v2.csv",
    "experiments/w2_integration/calibration_params.json",
    "experiments/w4_refs/crew_factors.csv",
    "experiments/w6_retrospective/zscore_params.json",
    "experiments/dist_margin_cover/residual_pool.csv",
    "experiments/rapm_multiseason/rapm_v1_*.csv",
    "evalharness/frozen_baselines.json",
)

# Directories never worth walking.
_SKIP_DIRS = {".git", "__pycache__", ".claude", "node_modules", ".venv", "venv"}


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #

class AsOfError(Exception):
    """Base class for as-of-invariant failures."""


class ManifestError(AsOfError):
    """A manifest is missing, malformed, or does not match its artifact."""


class AsOfViolation(AsOfError):
    """A fitted artifact's evidence does not strictly predate the forecast."""


# --------------------------------------------------------------------------- #
# time helpers
# --------------------------------------------------------------------------- #

def to_utc(value: Any) -> _dt.datetime:
    """Coerce a date / datetime / ISO string to a tz-aware UTC datetime.

    Naive inputs are interpreted as UTC (this repo's timestamps are either
    explicit UTC or plain game dates, never local-time-with-DST).  A bare
    ``date`` becomes midnight UTC — the conservative reading, since a game
    played "on" that date cannot be proven to precede midnight of it.
    """
    if isinstance(value, _dt.datetime):
        dt = value
    elif isinstance(value, _dt.date):
        dt = _dt.datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            raise ManifestError("empty timestamp string")
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = _dt.datetime.fromisoformat(s)
        except ValueError as exc:                       # pragma: no cover
            raise ManifestError(f"unparseable timestamp {value!r}: {exc}") from exc
    else:
        # duck-type pandas.Timestamp / numpy.datetime64 without importing pandas
        iso = getattr(value, "isoformat", None)
        if callable(iso):
            return to_utc(iso())
        raise ManifestError(f"unsupported timestamp type {type(value).__name__}")
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# content hashing + manifest paths
# --------------------------------------------------------------------------- #

def content_hash(path: str | os.PathLike) -> str:
    """SHA-256 of a file's bytes, streamed (artifacts can be hundreds of MB)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_path(artifact: str | os.PathLike) -> Path:
    """Sidecar path for an artifact: ``<artifact>.manifest.json``."""
    p = Path(artifact)
    if p.name.endswith(MANIFEST_SUFFIX):
        return p
    return p.with_name(p.name + MANIFEST_SUFFIX)


def _rel(path: Path, root: Path | None = None) -> str:
    """Path relative to ``root`` (default: the repo root), as posix."""
    base = Path(root).resolve() if root is not None else REPO_ROOT
    try:
        return path.resolve().relative_to(base).as_posix()
    except ValueError:
        return Path(path).as_posix()


# --------------------------------------------------------------------------- #
# write / read
# --------------------------------------------------------------------------- #

def write_manifest(
    artifact: str | os.PathLike,
    *,
    producer: str,
    fit_through_date: Any,
    fit_through_season: int,
    fit_seasons: Sequence[int] | None = None,
    notes: str = "",
    extra: Mapping[str, Any] | None = None,
) -> Path:
    """Write the sidecar manifest for ``artifact`` and return its path.

    ``fit_through_date`` must be the LATEST SOURCE OBSERVATION that influenced
    any fitted value in the artifact — not the build time.  Callers that pass a
    build time are silently defeating the invariant, so producers should derive
    it from the data (e.g. ``max(game_date)`` over the fit slice).
    """
    ap = Path(artifact)
    if not ap.exists():
        raise ManifestError(f"cannot manifest a nonexistent artifact: {ap}")
    fts = int(fit_through_season)
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "artifact": _rel(ap),
        "producer": str(producer),
        "fit_through_date": to_utc(fit_through_date).isoformat(),
        "fit_through_season": fts,
        "fit_seasons": [int(s) for s in (fit_seasons if fit_seasons is not None else [fts])],
        "content_sha256": content_hash(ap),
        "content_bytes": ap.stat().st_size,
        "created_at": _now(),
        "notes": str(notes),
    }
    if extra:
        for k, v in extra.items():
            if k in doc:
                raise ManifestError(f"extra key {k!r} collides with a reserved field")
            doc[k] = v
    mp = manifest_path(ap)
    mp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return mp


def read_manifest(artifact_or_manifest: str | os.PathLike) -> dict:
    """Load and structurally validate a manifest.

    Accepts either the artifact path or the manifest path.  Raises
    ``ManifestError`` if the sidecar is absent, unparseable, or missing a
    required field — never returns a partially-trusted dict.
    """
    mp = manifest_path(artifact_or_manifest)
    if not mp.exists():
        raise ManifestError(f"no manifest at {mp} — artifact is unattested")
    try:
        doc = json.loads(mp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest {mp} is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise ManifestError(f"manifest {mp} is not a JSON object")
    missing = [f for f in REQUIRED_FIELDS if f not in doc or doc[f] in (None, "")]
    if missing:
        raise ManifestError(f"manifest {mp} missing required field(s): {missing}")
    if doc["schema"] != SCHEMA:
        raise ManifestError(f"manifest {mp} schema {doc['schema']!r} != {SCHEMA!r}")
    to_utc(doc["fit_through_date"])          # parse-check, raises on garbage
    int(doc["fit_through_season"])           # type-check
    return doc


def verify_content(
    manifest: Mapping[str, Any],
    artifact: str | os.PathLike | None = None,
) -> str:
    """Re-hash the artifact and compare against the manifest.

    Returns the hash on success; raises ``ManifestError`` on drift.  A refit
    that forgets to rewrite its manifest fails here rather than being trusted.
    """
    ap = Path(artifact) if artifact is not None else (REPO_ROOT / str(manifest["artifact"]))
    if not ap.exists():
        raise ManifestError(f"artifact {ap} referenced by manifest does not exist")
    actual = content_hash(ap)
    if actual != manifest["content_sha256"]:
        raise ManifestError(
            f"content hash drift for {ap}: manifest says {manifest['content_sha256'][:12]}…, "
            f"file hashes to {actual[:12]}… — the artifact was rebuilt without "
            "updating its manifest; its fit_through claims are unverified")
    return actual


# --------------------------------------------------------------------------- #
# the invariant
# --------------------------------------------------------------------------- #

def assert_asof_metadata(
    artifact_manifest: Mapping[str, Any] | str | os.PathLike,
    decision_cutoff: Any,
    *,
    label: str = "",
) -> dict:
    """PURE METADATA comparison — no file access, no hashing.

    Raises ``AsOfViolation`` unless the manifest's latest source observation
    STRICTLY predates ``decision_cutoff``.  This is the date-logic half of the
    invariant, split out so unit tests can exercise it against synthetic
    manifests without materialising an artifact — and so the production entry
    point below can fail closed without those tests forcing a weaker default
    (screening_protocol_amendment_v5 C3(a)).

    ``decision_cutoff`` is the moment the forecast was COMMITTED, never the tip
    time and never the game date: tip time would credit information that
    arrived after the decision was made.
    """
    m = (artifact_manifest if isinstance(artifact_manifest, Mapping)
         else read_manifest(artifact_manifest))
    fit_through = to_utc(m["fit_through_date"])
    ft = to_utc(decision_cutoff)
    who = label or m.get("artifact", "<artifact>")
    if not (fit_through < ft):
        raise AsOfViolation(
            f"AS-OF VIOLATION: {who} (producer {m.get('producer', '?')}) has "
            f"fit_through_date {fit_through.isoformat()} which is NOT strictly "
            f"before decision_cutoff {ft.isoformat()}. The artifact's evidence "
            f"includes — or is simultaneous with — the row being scored.")
    return dict(m)


def assert_asof(
    artifact_manifest: Mapping[str, Any] | str | os.PathLike,
    forecast_time: Any,
    *,
    artifact: str | os.PathLike | None = None,
    verify_hash: bool = True,
    label: str = "",
) -> dict:
    """PRODUCTION entry point — FAILS CLOSED.

    Raises unless (a) the artifact's content hash still matches its manifest and
    (b) its latest source observation STRICTLY predates ``forecast_time``.

    ``verify_hash`` DEFAULTS TO TRUE (screening_protocol_amendment_v5 C3(b)).
    An opt-in integrity check only fires for the consumers who did not need
    reminding; the earlier False default is exactly how a rebuilt artifact could
    have kept an unchanged manifest.  Pass ``verify_hash=False`` explicitly ONLY
    inside a per-row loop that has already verified once for that run — and
    prefer :func:`assert_asof_metadata`, which says so in its name.

    ``forecast_time`` must be the DECISION CUTOFF, not tip time.

    Returns the manifest on success, so callers can chain.
    """
    m = (artifact_manifest if isinstance(artifact_manifest, Mapping)
         else read_manifest(artifact_manifest))
    if verify_hash:
        verify_content(m, artifact)
    return assert_asof_metadata(m, forecast_time, label=label)


def assert_scored_seasons_clean(
    artifact_manifest: Mapping[str, Any] | str | os.PathLike,
    scored_seasons: Iterable[int],
    *,
    label: str = "",
) -> dict:
    """Season-granularity companion to :func:`assert_asof`.

    Raises ``AsOfViolation`` if any scored season is inside the artifact's fit
    window, i.e. ``season <= fit_through_season`` (or is listed in
    ``fit_seasons``).  This is the check that would have caught rapm_v0 being
    used to score 2024 while fit through 2024.
    """
    m = (artifact_manifest if isinstance(artifact_manifest, Mapping)
         else read_manifest(artifact_manifest))
    fts = int(m["fit_through_season"])
    fit_seasons = {int(s) for s in m.get("fit_seasons", [])} or {fts}
    scored = sorted({int(s) for s in scored_seasons})
    bad = [s for s in scored if s <= fts or s in fit_seasons]
    if bad:
        who = label or m.get("artifact", "<artifact>")
        raise AsOfViolation(
            f"AS-OF VIOLATION (season): {who} is fit through season {fts} "
            f"(fit_seasons={sorted(fit_seasons)}) but is being used to score "
            f"season(s) {bad}. Those rows are inside the fit window.")
    return dict(m)


def check_asof(
    artifact_manifest: Mapping[str, Any] | str | os.PathLike,
    forecast_time: Any,
    **kwargs: Any,
) -> tuple[bool, str]:
    """Non-raising form: ``(ok, reason)``. For reporting loops and scanners.

    Delegates to :func:`assert_asof_metadata` — the DATE comparison only.
    Integrity is deliberately not folded in here: a scanner sweeping many
    artifacts should report as-of violations without a missing file turning
    into an indistinguishable failure, and the production path that must fail
    closed on both is :func:`assert_asof`.  Pass ``verify_hash``/``artifact``
    via ``kwargs`` to opt into hashing.
    """
    try:
        if kwargs.get("verify_hash"):
            assert_asof(artifact_manifest, forecast_time, **kwargs)
        else:
            kwargs.pop("verify_hash", None)
            kwargs.pop("artifact", None)
            assert_asof_metadata(artifact_manifest, forecast_time, **kwargs)
        return True, ""
    except AsOfError as exc:
        return False, str(exc)


# --------------------------------------------------------------------------- #
# scanner
# --------------------------------------------------------------------------- #

def _iter_repo_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            yield Path(dirpath) / fn


def scan_artifacts(
    root: str | os.PathLike | None = None,
    globs: Sequence[str] | None = None,
) -> list[dict]:
    """Inventory every known fitted artifact and report its manifest status.

    Returns one record per matched artifact::

        {artifact, matched_glob, exists, has_manifest, manifest_valid,
         hash_ok, fit_through_date, fit_through_season, producer, problem}

    Nothing is written and nothing is raised — this is the standing check that
    tells you which artifacts are still unattested.
    """
    r = Path(root or REPO_ROOT)
    pats = tuple(globs or FITTED_ARTIFACT_GLOBS)
    seen: dict[str, str] = {}
    for p in _iter_repo_files(r):
        rel = _rel(p, r)
        if rel.endswith(MANIFEST_SUFFIX):
            continue
        for pat in pats:
            if fnmatch.fnmatch(rel, pat):
                seen.setdefault(rel, pat)
                break
    out: list[dict] = []
    for rel in sorted(seen):
        pat = seen[rel]
        ap = r / rel
        rec: dict[str, Any] = {
            "artifact": rel,
            "matched_glob": pat,
            "exists": True,
            "has_manifest": manifest_path(ap).exists(),
            "manifest_valid": False,
            "hash_ok": "",
            "fit_through_date": "",
            "fit_through_season": "",
            "producer": "",
            "problem": "",
        }
        if not rec["has_manifest"]:
            rec["problem"] = "NO MANIFEST - artifact is unattested; consumers cannot assert as-of"
            out.append(rec)
            continue
        try:
            m = read_manifest(ap)
        except ManifestError as exc:
            rec["problem"] = f"INVALID MANIFEST: {exc}"
            out.append(rec)
            continue
        rec["manifest_valid"] = True
        rec["fit_through_date"] = m["fit_through_date"]
        rec["fit_through_season"] = m["fit_through_season"]
        rec["producer"] = m["producer"]
        try:
            verify_content(m, ap)
            rec["hash_ok"] = "yes"
        except ManifestError as exc:
            rec["hash_ok"] = "no"
            rec["problem"] = f"HASH DRIFT: {exc}"
        out.append(rec)
    # globs that matched nothing at all are themselves worth reporting
    matched_pats = set(seen.values())
    for pat in pats:
        if pat not in matched_pats:
            out.append({
                "artifact": pat, "matched_glob": pat, "exists": False,
                "has_manifest": False, "manifest_valid": False, "hash_ok": "",
                "fit_through_date": "", "fit_through_season": "", "producer": "",
                "problem": "GLOB MATCHED NO FILE — artifact absent or moved",
            })
    return out


def write_scan_csv(rows: Sequence[Mapping[str, Any]], path: str | os.PathLike) -> Path:
    """Write a scan result to CSV (the ``missing_manifests.csv`` deliverable)."""
    cols = ["artifact", "matched_glob", "exists", "has_manifest", "manifest_valid",
            "hash_ok", "producer", "fit_through_date", "fit_through_season", "problem"]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return p


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scan", action="store_true",
                    help="inventory fitted artifacts and report manifest status")
    ap.add_argument("--csv", default="", help="write the scan to this CSV path")
    ap.add_argument("--root", default="", help="repo root (default: this file's dir)")
    args = ap.parse_args(argv)
    if not args.scan:
        ap.print_help()
        return 0
    rows = scan_artifacts(args.root or None)
    missing = [r for r in rows if r["exists"] and not r["has_manifest"]]
    bad = [r for r in rows if r["has_manifest"] and (not r["manifest_valid"] or r["hash_ok"] == "no")]
    absent = [r for r in rows if not r["exists"]]
    for r in rows:
        flag = ("OK  " if r["manifest_valid"] and r["hash_ok"] == "yes"
                else "MISS" if r["exists"] and not r["has_manifest"]
                else "GONE" if not r["exists"] else "BAD ")
        print(f"{flag}  {r['artifact']}  {r['problem']}")
    print(f"\n{len(rows)} entries: {len(rows) - len(missing) - len(bad) - len(absent)} attested, "
          f"{len(missing)} UNATTESTED, {len(bad)} invalid/drifted, {len(absent)} absent")
    if args.csv:
        print("wrote", write_scan_csv(rows, args.csv))
    return 1 if (missing or bad) else 0


if __name__ == "__main__":
    sys.exit(_main())
