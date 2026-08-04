#!/usr/bin/env python3
"""register_p2_supersession.py — coordinator-only append of the P2 supersession records.

Workstream D produced PROPOSED records in
``turnover_p2_v1/PROPOSED_REGISTRY_RECORDS.jsonl``. Agents never append to the registry: four
integrity workstreams ran concurrently in one worktree, and concurrent appends to an append-only
JSONL are how a registry silently loses a record. The coordinator is the SINGLE WRITER.

This script reads the proposed records, stamps ``registered_at`` at append time (the proposed
values are placeholders written by the agent and are explicitly not authoritative), and appends
any that are not already present. Idempotent, keyed on ``experiment_id``, matching the convention
in ``register_tier_policy_erratum.py``.

Nothing already in the registry is mutated. P2 stands superseded AS RUN; it is not retroactively
repaired.

Run::

    python experiments/player_program/register_p2_supersession.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM_REGISTRY = HERE / "arm_registry.jsonl"
PROPOSED = HERE / "turnover_p2_v1" / "PROPOSED_REGISTRY_RECORDS.jsonl"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> int:
    proposed = _load(PROPOSED)
    if not proposed:
        print(f"no proposed records at {PROPOSED}")
        return 1

    existing = _load(ARM_REGISTRY)
    have = {r.get("experiment_id") for r in existing}

    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    written, skipped = [], []
    with ARM_REGISTRY.open("a", encoding="utf-8", newline="") as fh:
        for rec in proposed:
            eid = rec.get("experiment_id")
            if eid in have:
                skipped.append(eid)
                continue
            rec = dict(rec)
            # the agent's placeholder timestamp is not authoritative; the append time is.
            rec["registered_at"] = stamp
            rec["registered_by"] = "coordinator (single writer); record proposed by workstream D"
            fh.write(json.dumps(rec, sort_keys=False) + "\n")
            have.add(eid)
            written.append(eid)

    for eid in written:
        print(f"registered  {eid}")
    for eid in skipped:
        print(f"already present, skipped  {eid}")
    print(f"\n{len(written)} appended, {len(skipped)} skipped, "
          f"{len(existing) + len(written)} records total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
