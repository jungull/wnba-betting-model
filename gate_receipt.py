#!/usr/bin/env python3
"""gate_receipt.py — persist a Layer-A gate result as an artifact, not as prose.

WHY THIS EXISTS
---------------
Every gate run so far has been recorded by someone typing its numbers into a
handoff message. A supervisor reading that message has to take the transcription
on trust: nothing on disk says what `verify_all.py` actually returned, and a
mistyped count is indistinguishable from a real one. Run A13 existed only in
handoff prose, which is exactly the gap this closes.

This wraps `verify_all.py --repository-gate --json`, stamps the result with the
commit and tree state it was measured against, and writes a receipt file. The
receipt records what was measured, not what was claimed.

TWO KINDS OF RECEIPT, AND THEY ARE NOT INTERCHANGEABLE
------------------------------------------------------
* **producer-tree** — measured against a working tree that is normally dirty
  relative to HEAD, whose changes become the *next* commit. It certifies the tree
  that produced a commit, never the commit itself.
* **post-push clean-checkout** — measured against a clean checkout of an exact
  pushed commit. This is the only kind that certifies a commit.

A commit cannot contain its own post-push certification, so a post-push receipt
is written outside the repository (the supervisor workspace) and referenced by
digest. The `receipt_kind` field says which one you are holding; conflating them
is the error this field exists to prevent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECEIPT_SCHEMA = "layer_a_gate_receipt/1"
REPO = Path(__file__).resolve().parent


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()
    except Exception:
        return ""


def build(root: Path, *, receipt_kind: str, label: str = "") -> dict:
    """Run the repository gate and wrap its own JSON in a stamped receipt."""
    started = datetime.now(timezone.utc)
    proc = subprocess.run([sys.executable, "verify_all.py", "--repository-gate",
                           "--json"], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    ended = datetime.now(timezone.utc)

    try:
        payload = json.loads(proc.stdout)
    except Exception as exc:
        payload = {"parse_error": f"{type(exc).__name__}: {exc}",
                   "raw_stdout_tail": (proc.stdout or "")[-2000:]}

    dirty = [ln for ln in _git(root, "status", "--porcelain").splitlines() if ln.strip()]
    gate = payload.get("repository_gate", {})
    checks = gate.get("checks", [])

    # The per-suite counts come from each suite's own final line, not from a
    # number written down here. Every hard-coded count in this project has gone
    # stale; this one is parsed back out of the thing that produced it.
    per_suite, total = {}, 0
    for c in checks:
        summary = str(c.get("summary", ""))
        if "/" in summary and "tests passed" in summary:
            try:
                n = int(summary.split("/", 1)[0].strip().split()[-1])
                per_suite[c["name"]] = n
                total += n
            except (ValueError, IndexError):
                pass

    return {
        "schema": RECEIPT_SCHEMA,
        "receipt_kind": receipt_kind,
        "label": label,
        "generated_utc": started.isoformat().replace("+00:00", "Z"),
        "window": {"started_utc": started.isoformat().replace("+00:00", "Z"),
                   "ended_utc": ended.isoformat().replace("+00:00", "Z"),
                   "elapsed_seconds": round((ended - started).total_seconds(), 1)},
        "commit": _git(root, "rev-parse", "HEAD"),
        "commit_subject": _git(root, "log", "-1", "--pretty=%s"),
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "working_tree_clean_vs_head": not dirty,
        "n_dirty_paths": len(dirty),
        "exit_code": proc.returncode,
        "state": gate.get("state"),
        "n_checks": gate.get("n_checks"),
        "n_green": gate.get("n_green"),
        "per_suite_assertions": per_suite,
        "total_assertions": total,
        "checks": [{k: v for k, v in c.items() if k != "output"} for c in checks],
        "certifies_this_commit": (
            receipt_kind == "post_push_clean_checkout" and not dirty),
        "note": ("a producer-tree receipt certifies the tree that produced a commit, "
                 "NOT the commit; only a clean post-push checkout certifies a commit"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--kind", default="producer_tree",
                    choices=["producer_tree", "post_push_clean_checkout"])
    ap.add_argument("--label", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rec = build(Path(args.root), receipt_kind=args.kind, label=args.label)
    text = json.dumps(rec, indent=2, default=str) + "\n"

    # Write and hash the SAME bytes.
    #
    # This is the defect that produced the wrong A15 digest, and it lived in this tool rather
    # than in a human transcription: `Path.write_text` opens in text mode, so on Windows every
    # "\n" becomes "\r\n" on disk, while `text.encode()` hashed the pre-translation bytes. The
    # published digest therefore identified a LF-normalized transformation of the file that no
    # one hashing the actual file could ever reproduce. `newline=""` disables the translation,
    # and the digest is then taken from the bytes read back off disk rather than from the string
    # we hoped we wrote -- a receipt that certifies a gate must first be able to certify itself.
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    on_disk = Path(args.out).read_bytes()
    digest = hashlib.sha256(on_disk).hexdigest()
    if on_disk != text.encode("utf-8"):
        raise SystemExit(
            f"receipt bytes on disk differ from the bytes intended ({len(on_disk)} vs "
            f"{len(text.encode('utf-8'))}); refusing to publish a digest that names neither")
    print(f"wrote {args.out}")
    print(f"  state={rec['state']} {rec['n_green']}/{rec['n_checks']} "
          f"assertions={rec['total_assertions']} exit={rec['exit_code']}")
    print(f"  commit={rec['commit'][:12]} clean={rec['working_tree_clean_vs_head']}")
    print(f"  receipt_sha256={digest}")
    return 0 if rec["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
