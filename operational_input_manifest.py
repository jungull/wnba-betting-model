#!/usr/bin/env python3
"""Bind the git-ignored inputs that `daily_certify.py` requires.

The standing gate mixes two different kinds of evidence:

  * a **reproducible repository gate** — checks that pass from a clean checkout
    of a commit and nothing else;
  * an **environment-dependent operational certification** — `daily_certify`,
    which reads live capture files that are deliberately git-ignored
    (`.gitignore` lines 5 and 9) and therefore cannot travel with a commit.

A "9/9 green" claim that silently depends on the second kind is not
reproducible from the pushed commit. This script makes the dependency explicit
by emitting a deterministic manifest of every ignored input the operational
certification reads: relative path, byte size, SHA-256, capture/observation
timestamp, plus one aggregate hash over the whole set.

It computes no model output, reads no prediction or accuracy artifact, and
fits nothing. It only hashes files.

Usage:
    python operational_input_manifest.py            # manifest this checkout
    python operational_input_manifest.py --root R   # manifest checkout R
    python operational_input_manifest.py --out P    # write JSON to P
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

# The ignored inputs daily_certify.py actually reads, with the checks that need
# them. Frozen here so the manifest's scope is auditable rather than incidental.
REQUIRED_IGNORED: list[tuple[str, str, str]] = [
    # (kind, glob-or-path relative to repo root, consuming check)
    ("glob", "data/odds_capture/live_*.json",
     "odds capture freshness; game-day inference; odds stale-book detection; "
     "postponement / tip-time change detection; schema fingerprint "
     "(newest snapshot only)"),
    ("file", "data/odds_capture/capture_log.csv", "schema fingerprint drift"),
    ("file", "data/possessions/possessions.parquet", "schema fingerprint drift"),
]

STAMP_RE = re.compile(r"(\d{8})T(\d{6})Z")


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

    Returns (iso8601_utc, source) so a reader can tell a real capture stamp
    from a filesystem timestamp that may have been rewritten by a copy.
    """
    m = STAMP_RE.search(path.name)
    if m:
        d, t = m.groups()
        dt = datetime.strptime(d + t, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z"), "filename_capture_stamp"
    dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z"), "filesystem_mtime"


def is_git_ignored(root: Path, rel: str) -> bool:
    r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", rel],
                       capture_output=True)
    return r.returncode == 0


def git_head(root: Path) -> str:
    r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def dirty_tracked(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain",
                        "--untracked-files=no"], capture_output=True, text=True)
    return sorted(line.strip() for line in r.stdout.splitlines() if line.strip())


def build(root: Path) -> dict:
    entries: list[dict] = []
    missing: list[str] = []

    for kind, spec, consumer in REQUIRED_IGNORED:
        if kind == "glob":
            parent, pattern = spec.rsplit("/", 1)
            found = sorted((root / parent).glob(pattern)) if (root / parent).exists() else []
            if not found:
                missing.append(spec)
            paths = found
        else:
            p = root / spec
            paths = [p] if p.exists() else []
            if not paths:
                missing.append(spec)

        for p in paths:
            digest, size = sha256_of(p)
            obs, obs_src = observation_time(p)
            entries.append({
                "relative_path": p.relative_to(root).as_posix(),
                "bytes": size,
                "sha256": digest,
                "observed_utc": obs,
                "observed_from": obs_src,
                "git_ignored": is_git_ignored(root, p.relative_to(root).as_posix()),
                "consumed_by": consumer,
            })

    entries.sort(key=lambda e: e["relative_path"])

    # Aggregate hash over content identity only -- path, size, digest. Excludes
    # timestamps and commit so the same file set always hashes the same.
    agg = hashlib.sha256()
    for e in entries:
        agg.update(f"{e['relative_path']}\0{e['bytes']}\0{e['sha256']}\n".encode())

    return {
        "purpose": "bind the git-ignored inputs required by daily_certify.py",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "root_commit": git_head(root),
        "dirty_tracked_files": dirty_tracked(root),
        "n_entries": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "missing_required_inputs": missing,
        "aggregate_manifest_sha256": agg.hexdigest(),
        "aggregate_hash_domain": "sha256 over '<relative_path>\\0<bytes>\\0<sha256>\\n' "
                                 "for every entry, ordered by relative_path",
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

    print(f"\n{manifest['n_entries']} entries, "
          f"{manifest['total_bytes']} bytes, "
          f"aggregate {manifest['aggregate_manifest_sha256']}", file=sys.stderr)
    if manifest["missing_required_inputs"]:
        print(f"MISSING: {manifest['missing_required_inputs']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
