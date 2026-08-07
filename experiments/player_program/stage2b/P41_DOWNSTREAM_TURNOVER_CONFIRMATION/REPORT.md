# P41_DOWNSTREAM_TURNOVER_CONFIRMATION — Report

> SECONDARY EVIDENCE. Operational relevance only. A downstream result can never rescue an arm that failed or worsened the primary possession target.

## Verdict of this node in one paragraph

The carded population for downstream turnover scoring is **arms that passed the primary
possession gate only**. That population is **empty**: P40 adjudicated all 29 fitted elements
FAIL on the primary regulation-equivalent possession target (ratified by `D042_P40_CLOSE`).
Under the frozen P28 ordering contract (R1/R3), a candidate that fails the primary gate does
not enter the frozen turnover scorer, so **the scorer was not invoked, zero downstream
turnover numbers were computed, and no challenger downstream figure exists this cycle**. A
number that does not exist cannot rescue anything. This node is therefore a **reduced-scope
confirmation**, executed exactly as the card and D042 direct: the short honest node is the
correct result. All three acceptance criteria are satisfied — the first and third vacuously
(zero arms run, zero arms credited), the second positively (the scorer bytes are confirmed
identical to the P28 frozen pin, and unmodified is trivially also uninvoked).

## What was measured, and by what

Everything below was produced by one script committed in this node's scope:

```
python experiments/player_program/stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION/confirm_downstream.py
```

which printed `{"census_consistent": true, "zero_pass": true, "scorer_unmodified": true,
"gate_fails_closed": true, "line149_present": true}` and wrote `DOWNSTREAM.json`. The carded
validation command was run and passes:

```
python -c "import json;json.load(open('experiments/player_program/stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION/DOWNSTREAM.json'))"
```

**M1 — Primary-gate verdict census** (from
`stage2b/P40_PRIMARY_ADJUDICATION/ADJUDICATION.json`, `elements` block, cross-checked against
its `summary` block): 29 fitted elements; verdict distribution `{FAIL: 29}`; `n_pass_primary
= 0`; element-level census agrees with P40's own summary (`fitted_elements: 29`,
`n_pass_primary: 0`, `n_fail_primary: 29`). The authorized-entrant set for the frozen scorer,
derived mechanically as `verdict == "PASS"`, is the empty list. The full 29-row eligibility
table, each row carrying the P28 R3 refusal rule, is in `DOWNSTREAM.json`.

**M2 — The frozen scorer is byte-identical to its freeze.** sha256 of
`experiments/player_program/run_turnover_p1_universe_fix.py` measured this node:
`612e0543a98f2ef945b7e92ff6b0c75679f5c8253f0a983a031918b993d57338`. This equals both the
constant `FROZEN_SCORER_SHA256` pinned in P28's `ordering_contract.py` and the hash recorded
in P28's `MEASUREMENTS.json`. The scorer was neither modified nor invoked by this node.

**M3 — The documented pairing line, read from the bytes.** Line 149 of the scorer, verbatim:

```
        expo_t = g["team_off_possessions"] if name == "intrinsic" else g["projected_team_off_possessions"]
```

i.e. the operational track pairs *projected* (regulation-equivalent) exposure with raw
full-game outcomes — the documented mismatch, restated verbatim in `DOWNSTREAM.json` from
P28's `DOCUMENTED_MISMATCH` constant (11.0564 possessions on 132 OT rows / 66 clusters, 0.0
on non-OT rows). Restated, not repaired; the scorer stays frozen.

**M4 — Synthetic fail-closed test of the call-site gate** (permitted class: unit / synthetic
/ identity / schema). P28's `authorize_downstream()` was imported read-only and fed two
synthetic records (no real candidate record was fabricated, no downstream number computed):
a sealed record with verdict FAIL was refused with finding kind `primary_verdict_is_FAIL`;
an unsealed record was refused with finding kind `primary_verdict_not_sealed`. The gate
fails closed exactly as the contract asserts.

## Incumbent pathway

The operational downstream pathway is unchanged this cycle: the frozen incumbent
`D_ewma_shrunk` (K=200, alpha=0.1) continues to feed the frozen scorer at the documented
pairing. No challenger was authorized to enter the scorer and the scorer bytes are confirmed
frozen. **No new incumbent downstream score was computed here**: the card scopes scorer runs
to arms that passed this cycle's primary gate, and the incumbent is not such an arm — it is
the frozen benchmark. Its previously recorded operational figures stand unaltered.

## What could NOT be established, and why

* **Any challenger downstream turnover figure.** Not computed, by rule: P28 R3 prohibits
  computing a downstream number for a primary FAIL, and all 29 elements are primary FAILs.
  This is not a data gap; it is the contract operating as designed.
* **Whether any of this cycle's mechanisms would have moved downstream turnover MAE.**
  Unknowable without violating R1/R3. It stays unknown. (A07, the strongest surviving lead,
  is recorded by D042 for a *future preregistered cycle* only; it gets no downstream number
  from this cycle.)
* **A fresh incumbent downstream score.** Out of the card's scope (see above); deliberately
  not produced rather than half-produced.

## Contradictions found

None between the documents and the bytes consulted by this node. Specifically checked:
P40's element-level verdicts vs. its own summary block (consistent); the scorer bytes vs.
the P28 pin and the P28 measurement record (identical, three-way); line 149 vs. the pairing
recorded in `EVIDENCE_PACKET_V2.downstream_operational_boundary.recorded_pairing` (the cited
consumer line exists and does what the packet says it does).

## Stop conditions

None tripped. Nothing found here would change the primary target, the K0 structure, the
inference structure, the candidate universe, the cutoff-valid feature set, or the leakage
status. The zero-pass outcome is upstream fact, not a finding of this node.

## Files written (all inside this node's write scope)

* `confirm_downstream.py` — the measurement script (sole producer of every number above)
* `DOWNSTREAM.json` — required machine-readable output (validated with the carded command)
* `REPORT.md` — this report

No frozen artifact was modified. No sealed result was read. Git was not run.