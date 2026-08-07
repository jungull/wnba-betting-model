#!/usr/bin/env python3
"""confirm_downstream.py -- P41_DOWNSTREAM_TURNOVER_CONFIRMATION under a zero-pass upstream verdict.

The card mandates downstream turnover scoring for arms that passed the primary possession
gate ONLY. P40 adjudicated 0/29 passes (ratified D042_P40_CLOSE). This script therefore does
NOT run the frozen scorer on anything. What it does, measured against actual bytes:

  M1  Census the P40 adjudicated verdicts: count PASS / FAIL per element, cross-check the
      element-level census against P40's own summary block. The authorized entrant set for
      the frozen turnover scorer is derived mechanically: verdict == "PASS".
  M2  Hash the frozen scorer (run_turnover_p1_universe_fix.py) and compare against the
      contract constant FROZEN_SCORER_SHA256 pinned in P28's ordering_contract.py and
      against the hash recorded in P28's MEASUREMENTS.json. Confirms "used unmodified"
      in the only sense applicable this cycle: unmodified, and not invoked.
  M3  Read line 149 of the scorer verbatim -- the documented raw/regulation-equivalent
      pairing line -- and record it.
  M4  SYNTHETIC fail-closed test (permitted: unit/synthetic/identity/schema tests only):
      feed authorize_downstream() a synthetic sealed record with verdict FAIL and confirm
      the contract refuses it; feed it a synthetic UNSEALED record and confirm refusal.
      No real candidate record is fabricated and no downstream number is computed.

This module imports P28's ordering_contract read-only. It modifies no frozen artifact.
Writes only inside stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION/.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # .../stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION
STAGE2B = HERE.parent
PP = STAGE2B.parent                               # .../experiments/player_program

ADJUDICATION = STAGE2B / "P40_PRIMARY_ADJUDICATION" / "ADJUDICATION.json"
P28_DIR = STAGE2B / "P28_PRIMARY_SECONDARY_ORDERING_CONTRACT"
P28_MEASUREMENTS = P28_DIR / "MEASUREMENTS.json"
SCORER = PP / "run_turnover_p1_universe_fix.py"
OUT = HERE / "DOWNSTREAM.json"

EPISTEMIC_STATUS = ("SECONDARY EVIDENCE. Operational relevance only. A downstream result can "
                    "never rescue an arm that failed or worsened the primary possession target.")


def load_ordering_contract():
    """Import P28's ordering_contract.py read-only, without touching sys.path for other modules."""
    spec = importlib.util.spec_from_file_location(
        "p28_ordering_contract", P28_DIR / "ordering_contract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    oc = load_ordering_contract()

    # ---------------- M1: verdict census and the authorized entrant set ----------------
    adj = json.loads(ADJUDICATION.read_text(encoding="utf-8"))
    elements = adj["elements"]
    census = {}
    authorized_entrants = []
    eligibility = []
    for element_id, rec in sorted(elements.items()):
        v = rec.get("verdict")
        census[v] = census.get(v, 0) + 1
        entered = (v == "PASS")   # R1/R3: only a sealed primary PASS may enter the frozen scorer
        if entered:
            authorized_entrants.append(element_id)
        eligibility.append({
            "element_id": element_id,
            "arm_id": rec.get("arm_id"),
            "family": rec.get("family"),
            "primary_verdict": v,
            "authorized_for_frozen_turnover_scorer": entered,
            "refusal_rule": None if entered else
                "P28 R3: a candidate that fails the primary possession-target gate does not "
                "enter the frozen turnover scorer",
        })

    summary = adj["summary"]
    census_consistent = (
        summary.get("n_pass_primary") == census.get("PASS", 0)
        and summary.get("n_fail_primary") == census.get("FAIL", 0)
        and summary.get("fitted_elements") == len(elements)
    )

    # ---------------- M2: the frozen scorer is byte-identical to the P28-pinned hash ----------------
    measured_scorer_sha = sha256_file(SCORER)
    contract_sha = oc.FROZEN_SCORER_SHA256
    p28_meas = json.loads(P28_MEASUREMENTS.read_text(encoding="utf-8"))
    # P28 recorded the scorer hash in its frozen-input hash block; locate it by filename key.
    p28_recorded_sha = None
    def find_hash(obj):
        nonlocal p28_recorded_sha
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.endswith("run_turnover_p1_universe_fix.py") and isinstance(v, str):
                    p28_recorded_sha = v
                find_hash(v)
        elif isinstance(obj, list):
            for it in obj:
                find_hash(it)
    find_hash(p28_meas)

    scorer_unmodified = (measured_scorer_sha == contract_sha == p28_recorded_sha)

    # ---------------- M3: the documented pairing line, read from the bytes ----------------
    lines = SCORER.read_text(encoding="utf-8").splitlines()
    line_149 = lines[oc.FROZEN_SCORER_LINE - 1] if len(lines) >= oc.FROZEN_SCORER_LINE else None

    # ---------------- M4: synthetic fail-closed tests of the call-site gate ----------------
    synth_fail = {"sealed": True, "primary_verdict_digest": "0" * 64, "verdict": "FAIL"}
    r_fail = oc.authorize_downstream(synth_fail, raise_on_block=False)
    synth_unsealed = {"sealed": False, "primary_verdict_digest": "0" * 64, "verdict": "PASS"}
    r_unsealed = oc.authorize_downstream(synth_unsealed, raise_on_block=False)
    gate_fails_closed = (r_fail["authorized"] is False) and (r_unsealed["authorized"] is False)

    out = {
        "schema": "stage2b_p41_downstream_turnover_confirmation/1",
        "node": "P41_DOWNSTREAM_TURNOVER_CONFIRMATION",
        "epistemic_status": EPISTEMIC_STATUS,
        "upstream_authority": {
            "primary_adjudication": "stage2b/P40_PRIMARY_ADJUDICATION/ADJUDICATION.json",
            "ratification": "D042_P40_CLOSE (DECISION_LEDGER.jsonl): sweep of nulls is the "
                            "verified scientific outcome; P41 proceeds per its card",
            "ordering_contract": "P28 PRIMARY_SECONDARY_ORDERING_CONTRACT_v1, rules R1/R3 "
                                 "(frozen; enforced at the call site, never edited)",
        },
        "primary_gate_census": {
            "fitted_elements": len(elements),
            "verdicts": census,
            "n_pass_primary": census.get("PASS", 0),
            "n_fail_primary": census.get("FAIL", 0),
            "consistent_with_p40_summary_block": census_consistent,
        },
        "authorized_entrants_to_frozen_scorer": authorized_entrants,
        "arms_scored_downstream": [],
        "downstream_numbers_computed": 0,
        "no_op_statement": (
            "The carded population for downstream turnover scoring is 'arms that passed the "
            "primary possession gate only'. That set is EMPTY: all 29 fitted elements carry an "
            "adjudicated primary verdict of FAIL. Under P28 R1/R3 no candidate may enter the "
            "frozen turnover scorer, so the scorer was NOT invoked and no downstream turnover "
            "number exists for any challenger this cycle. A number that does not exist cannot "
            "rescue anything. This node is a reduced-scope confirmation, not a scoring run."
        ),
        "frozen_scorer": {
            "file": "experiments/player_program/run_turnover_p1_universe_fix.py",
            "sha256_measured_this_node": measured_scorer_sha,
            "sha256_pinned_in_p28_contract": contract_sha,
            "sha256_recorded_in_p28_measurements": p28_recorded_sha,
            "byte_identical_to_frozen_pin": scorer_unmodified,
            "invoked_this_node": False,
            "modified_this_node": False,
            "pairing_line_number": oc.FROZEN_SCORER_LINE,
            "pairing_line_verbatim": line_149,
        },
        "documented_mismatch_restated": dict(oc.DOCUMENTED_MISMATCH),
        "incumbent_pathway_confirmation": {
            "incumbent": "D_ewma_shrunk (frozen; K=200, alpha=0.1)",
            "statement": (
                "The operational downstream pathway is unchanged this cycle: the frozen "
                "incumbent D_ewma_shrunk continues to feed the frozen turnover scorer at the "
                "documented raw/regulation-equivalent pairing. No challenger was authorized to "
                "enter the scorer, no challenger downstream figure exists, and the scorer bytes "
                "are confirmed identical to the P28-pinned freeze. No NEW incumbent downstream "
                "score was computed here: the card scopes scorer runs to arms that passed this "
                "cycle's primary gate, and the incumbent is not such an arm -- it is the frozen "
                "benchmark. Its previously recorded operational figures stand unaltered."
            ),
        },
        "acceptance_criteria": {
            "only_arms_that_passed_primary_gate_are_run": {
                "satisfied": True,
                "how": "zero arms passed; zero arms were run (vacuous satisfaction, measured "
                       "from the adjudicated verdict census)",
            },
            "frozen_turnover_scorer_used_unmodified": {
                "satisfied": True,
                "how": "the scorer was not invoked (no authorized entrant) and its bytes are "
                       "sha256-identical to the P28 frozen pin",
            },
            "no_arm_credited_for_exploiting_mismatch": {
                "satisfied": True,
                "how": "no downstream number was computed for any arm, so no credit of any "
                       "kind -- mismatch-derived or otherwise -- was assigned (vacuous "
                       "satisfaction)",
            },
        },
        "synthetic_gate_tests": {
            "description": "fail-closed identity tests of P28 authorize_downstream; synthetic "
                           "records only, no real candidate fabricated, no downstream number "
                           "computed",
            "sealed_FAIL_record_refused": r_fail["authorized"] is False,
            "unsealed_record_refused": r_unsealed["authorized"] is False,
            "refusal_findings_kinds": {
                "sealed_FAIL": [f["kind"] for f in r_fail["findings"]],
                "unsealed": [f["kind"] for f in r_unsealed["findings"]],
            },
            "gate_fails_closed": gate_fails_closed,
        },
        "downstream_may_overturn_primary": False,
        "stop_conditions_tripped": [],
        "eligibility_table": eligibility,
    }

    checks = {
        "census_consistent": census_consistent,
        "zero_pass": census.get("PASS", 0) == 0,
        "scorer_unmodified": scorer_unmodified,
        "gate_fails_closed": gate_fails_closed,
        "line149_present": line_149 is not None,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(checks, indent=1))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
