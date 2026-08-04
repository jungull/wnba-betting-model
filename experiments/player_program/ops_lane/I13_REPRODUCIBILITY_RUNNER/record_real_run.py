#!/usr/bin/env python3
"""record_real_run.py — record the one REAL run this node ships, into runs/universe_census/.

Re-running this OVERWRITES the recorded manifest and the recorded outputs. That is deliberate and
it is also why it is a separate script from ``TESTS.py``: verification must never be able to
repair its own subject. ``TESTS.py`` only ever calls ``verify()``, which writes to a scratch
directory and then deletes it.

Run:  python record_real_run.py
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from pathlib import Path                                                      # noqa: E402

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))

import repro_runner as rr                                                     # noqa: E402

SEED = 20260804
RUN = HERE / "runs" / "universe_census"

INPUTS = {
    "team_possession_prior": PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet",
    "possessions_raw_v2": PROGRAM / "possessions_v2" / "possessions_raw_v2.parquet",
    "exposure_receipt": PROGRAM / "projected_exposure_v1" / "PROJECTED_EXPOSURE_RECEIPT.json",
    "exposure_validation": PROGRAM / "projected_exposure_v1" / "PROJECTED_EXPOSURE_VALIDATION.json",
    "possessions_receipt": PROGRAM / "possessions_v2" / "POSSESSION_INTEGRITY_RECEIPT_V2.json",
}


def main() -> int:
    m = rr.record(
        RUN,
        payload=HERE / "payload_universe_census.py",
        argv_tail=["--out", "{OUT}"],
        inputs=INPUTS,
        seed=SEED,
        python_hash_seed=0,
        declared_sources=[HERE / "payload_universe_census.py", HERE / "_repro_exec.py"],
        description=("structural census of the frozen team-game possession universe plus a seeded "
                     "cluster bootstrap of the target column. Read-only; no model is fitted and "
                     "no arm is scored."),
    )
    print(f"recorded {m['run_name']}  run_id={m['run_id']}")
    print(f"  commit        : {m['code']['commit']}")
    print(f"  seed          : {m['seeds']['seed']} / PYTHONHASHSEED={m['seeds']['python_hash_seed']}")
    print(f"  inputs bound  : {len(m['inputs'])}")
    print(f"  sources bound : {len(m['code']['sources'])}")
    for rel in sorted(m["code"]["sources"]):
        print(f"      {rel}")
    print(f"  outputs bound : {len(m['outputs'])}")
    for name, rec in sorted(m["outputs"].items()):
        print(f"      {name}  {rec['sha256'][:16]}...  {rec['bytes']} bytes")
    print(f"  manifest digest: {m['manifest_digest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
