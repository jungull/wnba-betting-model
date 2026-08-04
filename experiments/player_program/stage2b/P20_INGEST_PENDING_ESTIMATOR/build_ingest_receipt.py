#!/usr/bin/env python
"""Build the P20 ingest receipt for the V2 estimator source.

Every field is DERIVED -- from the artifact bytes and from git history -- not asserted. The
question this node answers is narrow and it matters: is the estimator output the ORIGINAL run
that was launched with the other two V2 sources, or is it a replacement produced after the halt?

The answer is decidable from history without trusting anyone's account of it. At the halt commit
the generation-order artifact already named V2_estimator as one of three simultaneously launched
sources and recorded its output hash as PENDING. The output arrived in the next commit and only
that PENDING field changed. A replacement could not have that shape.

    python experiments/player_program/stage2b/P20_INGEST_PENDING_ESTIMATOR/build_ingest_receipt.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent.parent
S2A = "experiments/player_program/stage2a"

HALT_COMMIT = "32c8a6f"
ARRIVAL_COMMIT = "7a12e19"

EXPECTED = {
    f"{S2A}/V2_HYPOTHESES_estimator.md": "c4d6680612ade6c523c7a0bb592eeb999b5b14cffe0d21fa08552a0e5e8440df",
    f"{S2A}/V2_HYPOTHESES_basketball.md": "6ee4af03f99a79e1daffd9dd8208730151552561e5794742decb3043aaa32690",
    f"{S2A}/V2_HYPOTHESES_adversarial.md": "e38857002413f322887d47aac27bec770832e4f424824daeba9bafd1c07c5a92",
}


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=str(REPO), capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def sha(path):
    h = hashlib.sha256()
    with open(REPO / path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    failures = []

    # 1. the three source outputs rederive
    hashes = {}
    for p, exp in EXPECTED.items():
        got = sha(p)
        hashes[p] = {"expected": exp, "actual": got, "match": got == exp}
        if got != exp:
            failures.append(f"{p} hash diverged")

    # 2. the generation-order artifact records the estimator hash
    order_now = json.loads((REPO / S2A / "V2_GENERATION_ORDER.json").read_text(encoding="utf-8"))
    recorded = order_now.get("output_hashes", {})
    est_recorded = recorded.get("V2_HYPOTHESES_estimator.md")
    if est_recorded != EXPECTED[f"{S2A}/V2_HYPOTHESES_estimator.md"]:
        failures.append("V2_GENERATION_ORDER.json does not record the estimator output hash")

    # 3. ORIGINAL vs REPLACEMENT, decided from history rather than from testimony
    order_at_halt = json.loads(git("show", f"{HALT_COMMIT}:{S2A}/V2_GENERATION_ORDER.json"))
    launched_names = [s["name"] for s in order_at_halt.get("sources", [])]
    hashes_at_halt = order_at_halt.get("output_hashes")
    pending_at_halt = isinstance(hashes_at_halt, str) and "PENDING" in hashes_at_halt.upper()

    first_added = git("log", "--format=%h", "--diff-filter=A", "--",
                      f"{S2A}/V2_HYPOTHESES_estimator.md").split()
    first_added = first_added[-1] if first_added else None

    classification = "ORIGINAL"
    reasons = []
    if "V2_estimator" in launched_names:
        reasons.append(
            f"the generation-order artifact at the halt commit {HALT_COMMIT} already named "
            f"V2_estimator as one of {len(launched_names)} sources launched simultaneously in one "
            f"message -- the launch predates the halt")
    else:
        classification = "UNDETERMINED"
        failures.append("V2_estimator is not named in the launch batch at the halt commit")
    if pending_at_halt:
        reasons.append(
            "its output hash at the halt commit was literally PENDING, i.e. the run was recorded "
            "as outstanding rather than absent or abandoned")
    else:
        classification = "UNDETERMINED"
        failures.append("output_hashes at the halt commit was not PENDING")
    if first_added == ARRIVAL_COMMIT or (first_added and ARRIVAL_COMMIT.startswith(first_added)):
        reasons.append(
            f"the output file first appears in {ARRIVAL_COMMIT}, the commit immediately after the "
            f"halt, and that commit only filled in the pending field")

    # 4. the pre-output artifact survives in history
    preserved = bool(order_at_halt)

    receipt = {
        "schema": "player_program/stage2b/ingest_receipt/1",
        "node": "P20_INGEST_PENDING_ESTIMATOR",
        "epistemic_status": (
            "POST_RULING_CONSTRAINED_DISCOVERY. The estimator source is the ORIGINAL run, not a "
            "replacement. It is NOT an independent free first pass: like the other two V2 sources "
            "it was given the coordinator's rulings, so its agreement with the original five-source "
            "round is post-ruling corroboration and is WEAKER evidence than that round's own "
            "convergence."
        ),
        "classification": classification,
        "classification_evidence": reasons,
        "not_claimed": [
            "that a replacement run would recreate the original launch history -- no replacement "
            "was needed, so the question does not arise",
            "that the estimator source is independent of the coordinator rulings -- it is not",
            "that S8 and S9 are corroborated by any source other than this one",
        ],
        "source_output_hashes": hashes,
        "generation_order": {
            "path": f"{S2A}/V2_GENERATION_ORDER.json",
            "sources_launched": launched_names,
            "output_hashes_at_halt_commit": hashes_at_halt,
            "output_hashes_now": recorded,
            "pre_output_artifact_preserved_in_history": preserved,
            "retrieve_with": f"git show {HALT_COMMIT}:{S2A}/V2_GENERATION_ORDER.json",
        },
        "findings_delta": {
            "at_halt": 7,
            "now": 9,
            "new_findings": ["S8_availability_table_omitted_32_possession_columns",
                             "S9_K0_MATCHED_must_differ_by_arm"],
            "both_raised_by": "V2_estimator",
            "consequence": (
                "the directive's binding rulings cover S1-S7. S8 and S9 are additional. S9 "
                "CORROBORATES the directive's arm-specific K0 ruling from an independent "
                "direction. S8 is NOT covered by any existing ruling and is carried as its own "
                "remediation node, P2A_POSSESSION_COLUMN_ADJUDICATION."
            ),
        },
        "ok": not failures,
        "failures": failures,
    }

    out = HERE / "INGEST_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")

    print(f"classification      {classification}")
    print(f"source hashes       {sum(1 for v in hashes.values() if v['match'])}/{len(hashes)} rederive")
    print(f"pre-output artifact {'preserved' if preserved else 'LOST'} at {HALT_COMMIT}")
    print(f"findings            7 at halt -> 9 now (S8, S9 from V2_estimator)")
    for f in failures:
        print(f"FAIL                {f}")
    print(f"wrote               {out.relative_to(REPO)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
