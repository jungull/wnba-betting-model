#!/usr/bin/env python
"""Freeze the complete V2 halt packet.

This node does not re-adjudicate anything. It fixes, in one hashed artifact, exactly what the
V2 round established and exactly what remains open, so that every downstream remediation node
works from the same frozen statement and V3 can later be checked against it.

Two things it is careful about:

  * the nine findings are carried FORWARD, not summarised. A summary of a leakage finding is how
    a leakage finding gets lost.
  * the "not stop conditions but recorded" block is copied VERBATIM. Several entries there are
    explicitly NOT VERIFIED BY THE COORDINATOR, and that qualifier is load-bearing -- it is the
    difference between a measurement and a claim relayed from a single source.

    python experiments/player_program/stage2b/P21_FREEZE_V2_HALT_PACKET/build_halt_packet.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent.parent
S2A = REPO / "experiments/player_program/stage2a"

PINNED = {
    "EVIDENCE_PACKET.json": "f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e",
    "EVIDENCE_PACKET_V2.json": "3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c",
    "V2_HYPOTHESES_estimator.md": "c4d6680612ade6c523c7a0bb592eeb999b5b14cffe0d21fa08552a0e5e8440df",
    "V2_HYPOTHESES_basketball.md": "6ee4af03f99a79e1daffd9dd8208730151552561e5794742decb3043aaa32690",
    "V2_HYPOTHESES_adversarial.md": "e38857002413f322887d47aac27bec770832e4f424824daeba9bafd1c07c5a92",
    "V2_STOP_CONDITION.json": "a4dd090b2b38dfb4d37028e15daa10c689deb27269cde3d8b9cddd12fd92244d",
    "V2_GENERATION_ORDER.json": "1998d5fda12ece9554d1ace895d010e46ba647c526df0e5170ae12e1a5f340ce",
}

# Which remediation node owns each finding. A finding with no owner is how a Severity A issue
# survives a remediation wave, so this mapping is asserted here and checked against the graph.
OWNER = {
    "S1_master_team_minutes_is_an_exact_overtime_indicator": "P22_POSTGAME_SURROGATE_GUARD",
    "S2_team_cities_join_hazards": "P23_DIMENSION_CARDINALITY_GUARD",
    "S3_injury_history_has_two_cutoff_regimes": "P24_INJURY_REGIME_LEDGER",
    "S4_free_SLOPE_confound_comparison_gate_has_no_dimension_for_it": "P25_OFFSET_DEPENDENCY_GUARD",
    "S5_opponent_design_is_exactly_determined_by_its_own_offset": "P25_OFFSET_DEPENDENCY_GUARD",
    "S6_the_tier_partition_decides_the_wave_and_the_ruling_does_not_settle_it": "P26_ARM_SPECIFIC_K0_CONTRACT",
    "S7_per_fold_degeneracy_lands_on_the_control_itself": "P27_FOLD_LOCAL_ESTIMABILITY_GUARD",
    "S8_availability_table_omitted_32_possession_columns": "P2A_POSSESSION_COLUMN_ADJUDICATION",
    "S9_K0_MATCHED_must_differ_by_arm": "P26_ARM_SPECIFIC_K0_CONTRACT",
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    failures = []

    hashes = {}
    for name, exp in PINNED.items():
        p = S2A / name
        got = sha(p) if p.is_file() else None
        hashes[name] = {"expected": exp, "actual": got, "match": got == exp}
        if got != exp:
            failures.append(f"{name}: expected {exp[:12]}… got {(got or 'MISSING')[:12]}…")

    stop = json.loads((S2A / "V2_STOP_CONDITION.json").read_text(encoding="utf-8"))
    findings = stop["findings"]

    if len(findings) != 9:
        failures.append(f"expected 9 findings, found {len(findings)}")
    for k in findings:
        if k not in OWNER:
            failures.append(f"finding {k} has NO remediation owner -- it would survive the wave")

    graph = json.loads((REPO / "experiments/player_program/orchestration/PROGRAM_GRAPH.json")
                       .read_text(encoding="utf-8"))
    node_ids = {n["id"] for n in graph["nodes"]}
    for k, owner in OWNER.items():
        if owner not in node_ids:
            failures.append(f"finding {k} is owned by {owner}, which is not a node in the graph")

    carried = {}
    for key, f in findings.items():
        carried[key] = {
            "affects": f.get("affects"),
            "severity": f.get("severity"),
            "raised_by": f.get("raised_by", "V2_basketball"),
            "verified_by_coordinator": f.get("verified_by_coordinator", f.get("verified_by") is not None),
            "unresolved_at_freeze": f.get("unresolved", True),
            "remediation_node": OWNER.get(key),
            "measurement": f.get("measurement") or f.get("measurement_bias_share_of_MSE")
                           or f.get("measurement_pace_source_by_season"),
            "mechanism": f.get("mechanism"),
            "why_it_matters": f.get("why_it_matters"),
            "consequence": f.get("consequence"),
        }

    by_severity = {}
    for f in findings.values():
        s = str(f.get("severity", "?")).split()[0]
        by_severity[s] = by_severity.get(s, 0) + 1

    packet = {
        "schema": "player_program/stage2b/v2_halt_packet/1",
        "node": "P21_FREEZE_V2_HALT_PACKET",
        "epistemic_status": (
            "POST_RULING_CONSTRAINED_DISCOVERY, frozen. The three V2 sources are independent of "
            "the original five and of one another, but NOT of the coordinator rulings: "
            "EVIDENCE_PACKET_V2 told them the target unit was settled, which strata were "
            "withdrawn, and how the controls are defined. Their agreement with the original round "
            "is post-ruling CORROBORATION and is WEAKER evidence than that round's own "
            "convergence. This is NOT a final candidate-generation wave."
        ),
        "frozen_artifact_hashes": hashes,
        "sources": {
            "count": 3,
            "names": ["V2_estimator", "V2_basketball", "V2_adversarial"],
            "all_returned": stop.get("all_three_v2_sources_returned"),
            "note": "V2_estimator returned AFTER the halt was declared; it is the ORIGINAL run, "
                    "not a replacement -- see P20_INGEST_PENDING_ESTIMATOR/INGEST_RECEIPT.json",
        },
        "findings_count": len(findings),
        "findings_by_severity": by_severity,
        "findings": carried,
        "stop_conditions_triggered": stop.get("stop_conditions_triggered"),
        "item_7_status": stop.get("item_7_status"),
        "recorded_but_not_stop_conditions": stop.get("not_stop_conditions_but_recorded"),
        "verbatim_copy_note": (
            "recorded_but_not_stop_conditions is copied VERBATIM from V2_STOP_CONDITION.json and "
            "is NOT edited. Several entries carry the qualifier 'NOT verified by the coordinator'. "
            "That qualifier is load-bearing: it marks a figure relayed from a single source rather "
            "than a measurement the coordinator reproduced. Any downstream use must carry it."
        ),
        "unresolved_at_freeze": sorted(k for k, v in carried.items() if v["unresolved_at_freeze"]),
        "remediation_ownership": OWNER,
        "what_this_freeze_does_not_establish": [
            "that any finding has been remediated -- the remediation nodes are what do that",
            "that the nine findings are exhaustive; a later source may find a tenth",
            "that the figures in recorded_but_not_stop_conditions are correct -- most are "
            "explicitly unverified",
            "any candidate's accuracy, which no V2 source measured and none was permitted to",
        ],
        "ok": not failures,
        "failures": failures,
    }

    out = HERE / "V2_HALT_PACKET.json"
    out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    digest = sha(out)
    (HERE / "V2_HALT_PACKET.sha256").write_text(
        f"{digest}  V2_HALT_PACKET.json\n", encoding="utf-8", newline="\n")

    print(f"artifacts      {sum(1 for v in hashes.values() if v['match'])}/{len(hashes)} rederive")
    print(f"findings       {len(findings)} carried, by severity {by_severity}")
    print(f"unresolved     {len(packet['unresolved_at_freeze'])}")
    print(f"stop cond.     {len(stop.get('stop_conditions_triggered') or [])} triggered")
    print(f"owners         all {len(OWNER)} findings mapped to a graph node")
    for f in failures:
        print(f"FAIL           {f}")
    print(f"packet sha256  {digest}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
