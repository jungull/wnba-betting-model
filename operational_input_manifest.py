#!/usr/bin/env python3
"""Bind every non-committed input that `daily_certify.py` actually reads.

WHY THIS EXISTS
---------------
`verify_all.py` reports two different kinds of evidence:

  * the **repository gate** (currently 10 checks; `verify_all.REPOSITORY_CHECKS`
    is the authority) — passes from a clean checkout of a commit and nothing
    else;
  * the **operational certification** (`daily_certify`) — reads live capture
    files that are git-ignored, untracked, or dirty, and therefore cannot travel
    with a commit. It is one check that internally runs ten hooks; this script
    audits the inputs of all ten.

A "green" operational result is only meaningful if a reviewer can tell *what it
was run against*. A filename in a dirty-file list is **not** a content binding —
only a hash is. This script walks `daily_certify` check by check and hashes
every input the commit cannot bind: **ignored, untracked, or dirty-tracked**.

Inputs that are tracked and clean are audited and counted but not hashed: the
commit already binds them by construction.

Fail-closed: a required input set that resolves to nothing is reported in
`missing_required_inputs` and the process exits non-zero.

It computes no model output, reads no prediction or accuracy artifact, and fits
nothing. It only lists and hashes files.

Usage:
    python operational_input_manifest.py                 # manifest this checkout
    python operational_input_manifest.py --root R        # manifest checkout R
    python operational_input_manifest.py --out P         # write JSON to P
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# The audit table: one row per daily_certify check, naming every input it reads.
#
# `required` marks input sets whose absence must fail the manifest. Sets that
# daily_certify itself treats as optional (`if p.exists()`) are not required
# here either -- but if they DO exist and are non-committed, they are hashed.
# ---------------------------------------------------------------------------
CHECK_INPUTS: list[dict] = [
    # NOTE: data/wnba_gamelog_*.parquet is read by THREE checks
    # (daily_certify.py:156, :189, :375). Omitting it from these declarations
    # made the completeness claim false: a future dirty copy would have escaped
    # hashing while the manifest still reported "every input bound".
    {"check": "duplicate game/player rows",
     "globs": ["data/wnba_gamelog_*.parquet",
               "data/refresh_2026/gamelog_*.parquet"], "required": True},

    {"check": "coverage by season (pbp/misc/advanced)",
     "globs": ["data/wnba_gamelog_*.parquet",
               "data/refresh_2026/gamelog_*.parquet",
               "data/refresh_2026/misc/misc_*.parquet",
               "data/refresh_2026/advanced/advanced_*.parquet",
               "data/refresh_2026/pbp/pbp_*.parquet",
               "data/playbyplay/pbp_*.parquet"], "required": True},

    {"check": "odds capture freshness",
     "globs": ["data/odds_capture/live_*.json"], "required": True},

    {"check": "injury capture freshness",
     # newest_stamped() iterates the WHOLE raw/ directory, so the whole listing
     # is an input; injury_log.csv is read for its max capture_utc; and
     # is_game_day_today() reads the newest odds snapshot.
     "globs": ["data/injury_capture/raw/*",
               "data/injury_capture/injury_log.csv",
               "data/odds_capture/live_*.json"], "required": True},

    {"check": "schema fingerprint drift",
     "globs": ["data/wnba_gamelog_*.parquet",
               "data/refresh_2026/gamelog_*.parquet",
               "data/refresh_2026/misc/misc_*.parquet",
               "data/refresh_2026/advanced/advanced_*.parquet",
               "data/refresh_2026/pbp/pbp_*.parquet",
               "data/playbyplay/pbp_*.parquet",
               "data/injury_capture/injury_log.csv",
               "data/odds_capture/capture_log.csv",
               "data/derived/stints.parquet",
               "data/derived/starters.csv",
               "data/possessions/possessions.parquet",
               "data/odds_capture/live_*.json",
               "data/certify/schema_fingerprints.json"], "required": False},

    {"check": "possession reconciliation (recent-game sample)",
     "globs": ["data/playbyplay/pbp_*.parquet",
               "data/refresh_2026/pbp/pbp_*.parquet",
               "data/masters/master_team.parquet"], "required": True},

    {"check": "pbp score reconciliation (sampled+incremental)",
     "globs": ["data/playbyplay/pbp_*.parquet",
               "data/refresh_2026/pbp/pbp_*.parquet",
               "experiments/odds_audit_ext/pbp_full_reconciliation.csv"],
     "required": False},

    {"check": "odds stale-book detection",
     "globs": ["data/odds_capture/live_*.json"], "required": True},

    {"check": "postponement / tip-time change detection",
     "globs": ["data/odds_capture/live_*.json"], "required": True},

    # The artifact globs are IMPORTED from asof_invariant rather than restated,
    # so this audit cannot drift from the check it is auditing.
    {"check": "fitted-artifact manifests (amendment v5 C3)",
     "globs": "FITTED_ARTIFACT_GLOBS", "required": True},
]

#: Nested git worktrees live under .claude/ and are NOT operational inputs.
#: Without this, a `**` glob happily hashes every sibling worktree's copy.
EXCLUDED_PREFIXES = (".claude/", ".git/")


def _artifact_globs() -> list[str]:
    """The real fitted-artifact globs, plus their .manifest.json siblings."""
    try:
        from asof_invariant import FITTED_ARTIFACT_GLOBS
    except Exception:                       # auditing a checkout we cannot import
        return []
    out: list[str] = []
    for g in FITTED_ARTIFACT_GLOBS:
        out.append(g)
        out.append(g + ".manifest.json")
    return out

STAMP_RE = re.compile(r"(\d{8})T(\d{6})Z")


# ---------------------------------------------------------------------------
# git classification, batched -- per-file git calls are far too slow here
# ---------------------------------------------------------------------------

def _git(root: Path, args: list[str], stdin: str | None = None):
    # NOTE: stdin is sent as BYTES on purpose. With text=True, Python translates
    # "\n" to "\r\n" on Windows, git then treats the trailing "\r" as part of
    # each pathname, and `check-ignore --stdin` silently reports almost nothing.
    # That bug once mislabelled every ignored odds snapshot as "untracked".
    return subprocess.run(
        ["git", "-C", str(root)] + args, capture_output=True,
        input=stdin.encode("utf-8") if stdin is not None else None)


def _lines(raw: bytes) -> list[str]:
    return [ln for ln in raw.decode("utf-8", "replace").replace("\r\n", "\n").split("\n") if ln]


def _unquote(p: str) -> str:
    """git quotes paths containing specials as "path"; undo that."""
    return p[1:-1] if len(p) >= 2 and p[0] == '"' and p[-1] == '"' else p


def classify(root: Path, rels: list[str]) -> dict[str, str]:
    """Map each relative path to committed_clean | dirty_tracked | untracked | ignored."""
    tracked = {_unquote(x) for x in _lines(_git(root, ["ls-files"]).stdout)}

    dirty: set[str] = set()
    for line in _lines(_git(root, ["status", "--porcelain",
                                   "--untracked-files=no"]).stdout):
        if len(line) > 3:
            dirty.add(_unquote(line[3:].strip()))

    ignored: set[str] = set()
    if rels:
        out = _git(root, ["check-ignore", "--stdin"],
                   stdin="\n".join(rels) + "\n").stdout
        ignored = {_unquote(ln.strip()) for ln in _lines(out)}

    result = {}
    for r in rels:
        if r in ignored:
            result[r] = "ignored"
        elif r in dirty:
            result[r] = "dirty_tracked"
        elif r in tracked:
            result[r] = "committed_clean"
        else:
            result[r] = "untracked"
    return result


def sha256_of(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def observation_time(path: Path) -> tuple[str, str]:
    """Capture time from the filename stamp when present, else file mtime.

    The source is recorded so a copied mtime cannot masquerade as a capture time.
    """
    m = STAMP_RE.search(path.name)
    if m:
        d, t = m.groups()
        dt = datetime.strptime(d + t, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z"), "filename_capture_stamp"
    dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z"), "filesystem_mtime"


def resolve(root: Path, spec: str) -> list[Path]:
    out = []
    for p in root.glob(spec):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES):
            continue
        out.append(p)
    return sorted(out)


def build(root: Path) -> dict:
    # 1. resolve every declared input, remembering which checks consume it
    consumers: dict[str, set[str]] = {}
    missing: list[dict] = []
    for entry in CHECK_INPUTS:
        specs = _artifact_globs() if entry["globs"] == "FITTED_ARTIFACT_GLOBS" \
            else entry["globs"]
        for spec in specs:
            found = resolve(root, spec)
            if not found and entry["required"]:
                missing.append({"check": entry["check"], "glob": spec})
            for p in found:
                consumers.setdefault(p.relative_to(root).as_posix(), set()).add(entry["check"])

    rels = sorted(consumers)
    status = classify(root, rels)

    # 2. hash exactly what the commit cannot bind
    NONCOMMITTED = ("ignored", "dirty_tracked", "untracked")
    entries: list[dict] = []
    committed_count = 0
    for rel in rels:
        st = status[rel]
        if st == "committed_clean":
            committed_count += 1
            continue
        p = root / rel
        digest, size = sha256_of(p)
        obs, obs_src = observation_time(p)
        entries.append({
            "relative_path": rel,
            "git_status": st,
            "bytes": size,
            "sha256": digest,
            "observed_utc": obs,
            "observed_from": obs_src,
            "consumed_by": sorted(consumers[rel]),
        })

    entries.sort(key=lambda e: e["relative_path"])

    # 3. aggregate over content identity only -- path, size, digest. Excludes
    #    timestamps and commit so the same file set always hashes the same.
    agg = hashlib.sha256()
    for e in entries:
        agg.update(f"{e['relative_path']}\0{e['bytes']}\0{e['sha256']}\n".encode())

    by_status: dict[str, int] = {}
    for e in entries:
        by_status[e["git_status"]] = by_status.get(e["git_status"], 0) + 1

    return {
        "purpose": "bind every non-committed input daily_certify.py actually reads "
                   "(ignored, untracked, or dirty-tracked)",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "root_commit": (_lines(_git(root, ["rev-parse", "HEAD"]).stdout) or ["UNKNOWN"])[0],
        "checks_audited": [e["check"] for e in CHECK_INPUTS],
        "n_inputs_resolved": len(rels),
        "n_committed_clean_not_hashed": committed_count,
        "n_entries": len(entries),
        "entries_by_git_status": by_status,
        "total_bytes": sum(e["bytes"] for e in entries),
        "missing_required_inputs": missing,
        "aggregate_manifest_sha256": agg.hexdigest(),
        "aggregate_hash_domain": "sha256 over '<relative_path>\\0<bytes>\\0<sha256>\\n' "
                                 "for every entry, ordered by relative_path",
        "note_committed_inputs": "inputs that are tracked and clean are audited and counted "
                                 "above but deliberately not hashed -- the commit binds them",
        "entries": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    manifest = build(root)
    text = json.dumps(manifest, indent=2, sort_keys=False) + "\n"

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)

    print(f"\n{manifest['n_inputs_resolved']} inputs audited; "
          f"{manifest['n_committed_clean_not_hashed']} committed-clean (not hashed); "
          f"{manifest['n_entries']} non-committed hashed "
          f"{manifest['entries_by_git_status']}; "
          f"{manifest['total_bytes']} bytes; "
          f"aggregate {manifest['aggregate_manifest_sha256']}", file=sys.stderr)
    if manifest["missing_required_inputs"]:
        print(f"FAIL-CLOSED, missing required inputs: "
              f"{manifest['missing_required_inputs']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
