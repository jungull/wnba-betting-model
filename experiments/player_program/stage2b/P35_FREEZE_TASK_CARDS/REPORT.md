# P35_FREEZE_TASK_CARDS — REPORT

FROZEN PREREGISTRATION. Standing conditional authorisation: freezing happens automatically once every P34 Severity A finding is closed. Registry records are APPENDED; the existing 41 are never edited.

## What this node did

Applied the complete D026 mandate to the P33 preregistration draft and froze 23 fit-ready task cards
in `SPEC.json`. Every P34 Severity A finding is closed (A01, A04, A19 withdrawn; A11 repaired exactly
as D026 words it). Every Severity B required change from all seven P34 reviews is applied to the card
it touches. Multiplicity denominators are recomputed after the withdrawals. The three withdrawals and
their D026 bases are recorded in the cards AND in registry append payloads so no future wave can
resurrect them silently.

**Cards frozen: 23.** Arms entering the P36 fit set: **22** (A06 is PREREGISTERED_CONDITIONAL_NOT_FIT —
its own frozen deadline, "before the P35 task-card freeze", expired unmet: no schedule artifact exists
in scope, re-measured at this freeze). Fitted elements: **29** over **10** families.

**A11 repair: EXPRESSED EXACTLY.** Null pinned to the single blended column `[log_exposure | dblend_t(1)]`
with free beta; the two-free-mains gloss struck (preserved verbatim as struck text per the D026
preserved disagreement); the never-firing rho-interval kill replaced with the decidable per-element set
(per-element beta interval + thin-stratum concentration + sign kills). A11 does not withdraw.

## What I measured, with the exact commands

| measurement | command | result |
|---|---|---|
| P34 SPEC hash | `Get-FileHash ...P34.../SPEC.json -Algorithm SHA256` | `7cdc2e8031f7f664b648bfc3f350cf6764fc9f8723b3b766ba1fde60db7e8d02` — MATCHES pin |
| P33 SPEC hash | `Get-FileHash ...P33.../SPEC.json -Algorithm SHA256` | `066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093` — MATCHES pin |
| arm registry baseline | `Get-Content arm_registry.jsonl | Measure-Object -Line`; `Get-FileHash` | **41 records**, sha256 `4137d122c7aadb27d58d81c43280dd1ac3c0e887e5e9e960211df7e7e2ae5a31` |
| team_cities.csv (OP-5 pin) | `Get-FileHash data/reference/team_cities.csv` | `10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d`, 1,892 bytes — MATCHES the P23 measurement quoted by OP-5 |
| A06 receipt existence | `Get-ChildItem -Recurse experiments/player_program -Filter '*schedul*'` and `-Include '*preseason*'` | **zero matches** — no schedule artifact in scope at the freeze deadline |
| SPEC.json validity | `python -c "import json;json.load(open('experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json'))"` | passes |
| task-card freeze hash | `sha256(json.dumps(spec['task_cards'], sort_keys=True, separators=(',',':')))` | `ec5a9cf759531cd9584548192d8b07bdfa1328ed55d36bb777819b02129c1666` (embedded in SPEC and in the freeze payload; recomputed-vs-embedded match verified True) |
| final SPEC.json bytes | `Get-FileHash .../P35_FREEZE_TASK_CARDS/SPEC.json` | `68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32` |

All other numbers in the cards (44/162 pre-window rows, 7 and 15 zero-prior rows, end_reason level
counts, expansion support 0/0/0/0/46, effective decayed support 9-15, R2 0.7134, m_bar range, OT
prevalence 66/1,491, etc.) are carried FROM the hash-verified P34 review files and are cited to their
reviewer in place. This node did not re-run those measurements; it froze specifications, which is
feature-free work. Nothing was fitted; no performance number exists anywhere in this node's output;
nothing under SEALED_RESULTS was read.

## Mandate items and dispositions (complete)

1. **23 frozen task cards carrying the complete P33 record amended by every Severity B** — DONE.
   Cards carry the P33 record by hash reference (`carry_convention`) plus enumerated amendments; every
   card lists its `amendments_applied` with the source finding IDs.
2. **A11 pinned repair exactly as D026 words it** — DONE (`a11_repair`); expressed exactly, so the
   withdrawal clause is not triggered. Fold-1 evaluability additionally pinned (F5) and the 0/0
   expansion-debut case covered (OP-2).
3. **Three withdrawals recorded with D026 bases** — DONE (`withdrawals` + three registry payloads,
   each with an explicit resurrection bar; A01's bar names the USER gate).
4. **Multiplicity family denominators recomputed** — DONE (`multiplicity_recomputed`): CAL 3;
   timeseries 10; COLDSTART 5 (A14 fixed slot, ordering over 4); lagged_pace 1; LAGGED_TEMPO_MIX 1
   (restated single-member, joint-scoring rule voided explicitly); EQC 1; PERSONNEL 1; SCHEDULE_FATIGUE 1;
   schedule_context 3; OPPONENT_F1 3. Total 29 fitted elements. Also closed: B-1 (option iii, express
   disclaimer + additive-funding acknowledgment + both-pass rule naming A17/A18 and A23/A24), B-2
   (A06-under-COLDSTART pinned as the binding alternate; temporal_drift annotated subset-vacuous), B-3
   (hold-others-at-primary compositions enumerated; asymmetry accepted with direction stated), B-4
   (regime (i): every grid element fitted end-to-end; selection glosses struck; multi-survivor rule),
   B-5 ('family-corrected' struck from kills; direction consequence stated), B-6 (LTM rule voided;
   A13 fixed-sequence level pinned), B-7 (both-pass joint re-test at R2 >= 0.25; per-family-Holm-only
   alpha declaration, additive bound 0.50 stated).
5. **Per-arm declared_family + TRUTHFUL recalibration declarations** — DONE: SUBSTANTIVE for every
   fitted arm; recalibration_declaration NOT_APPLICABLE everywhere (no RECALIBRATION arm survives);
   the false-attestation channel that killed A01 is structurally closed this cycle.
6. **Intercept structure per arm AND null + no-implementation-default-intercept invariant** — DONE
   (`intercept_structure`): free global intercept in A07/A12/A13/A14/A15 (arm and null identically);
   none anywhere else; violation voids the arm.
7. **Quasi-Poisson vs V2-retirement disposal in writing** — DONE
   (`quasi_poisson_v2_retirement_disposal`): the V2 sentence quoted in full; retirement scoped to
   challenger accuracy families; 0.193 scoped to constant-dispersion cancellation in the quasi-score;
   dispersion-heterogeneity caveat recorded; the HALT fork recorded, not exercised; per-arm
   response-family deviation voids the arm.
8. **d_t league-mean window (K-free, shared) and n_i contract-schedule clock** — DONE
   (`construction_pins`): all-prior K-free league mean shared across A08/A09/A10/A11; n counts on the
   2,990-row contract schedule including universe-excluded games; plus the A08 (game_date, game_id)
   tie-break and the A26 as-of-g LOO clock (L6).
9. **A16 opening-day NULL-row handling frozen identically in arm and null** — DONE
   (`opening_day_null_row_handling_frozen` on the A16 card): claim corrected to 2,982/2,990;
   unresolved prior games contribute no dev term; partial windows as-is; empty window -> dev := 0.
10. **A23 bundle_AI per the leakage L2 options** — DONE (option (i)): redefined to "previous COMPLETED
    same-season game" with the unimplementability of the scheduled reading stated in the frozen record
    (also closes OP-4); bundles differ in cap and opener rule only, honestly; K8 row-set note recorded.
11. **A13 cbar_F training-only** — DONE (L4): cbar_F and the n=0 imputation constant are TRAINING-row
    means, computed once per fold, held fixed across bootstrap refits, identical in arm and null.
12. **A06 repair path (b) bound to L3** — DONE (`a06_conditional_disposition.path_b_bound_to_L3`):
    hash-pinned formula, per-column S8/P2A adjudication, P22 invocation, permanent P34-unreviewed note,
    2-element cap (OP-10), registry append required. A06 itself: NOT FIT this cycle (measured — no
    receipt landed by its own frozen deadline); 2 conditional elements out of the CAL denominator.

Also applied (Severity B items not separately named in the dispatch): A08's self-contradictory
window constraint struck and replaced with the L_t := 0 rule (F1/OP-3 — the arm does not evaporate and
the timeseries denominator stays 10); deterministic symmetric empty-window rules for A09/A10/A11/A16
and the share-imputation rule for A17/A21 (F2/OP-2); A14 fixed Holm slot (F3) and single-franchise
confound/effective-support licensing caveats (F4); S7_TIER_SUPPORT_v1 registered per invoking arm via
registry payloads (F6 — A03/A12/A13/A14; A04 withdrawn); P26 K0 records emitted per card with the R8
scope adjudication and a named call site (K3); K5 relabel; K7/OP-6 symmetric NA and non-convergence
rules; OP-5 team_cities pin; OP-7 A22 correction; OP-8 fail-degrade semantics + drift diagnostic on
A20 (whose turnover dictionary is frozen as E_TO = {"turnover"}); C-level records carried (containment
restatement, turnover-lane scoping of citation 3, A02 first-order gloss and whole-game caveat, A26 OT
prevalence bracket, not-fold-blind note, A03 test-side support).

## Registry appends

The prompt requires appends by a SINGLE WRITER while this node's write scope excludes
`arm_registry.jsonl` (frozen artifact, standing rule 3). Disposition: the nine append payloads are
frozen verbatim in `SPEC.json.registry_append.payloads`; the **coordinator is the single writer** and
performs the append at integration after validation. Pre-append baseline recorded (41 records, sha256
above) so byte-identity of the existing records is verifiable after the append. Payloads: 1 freeze
record (carrying the task-card hash), 3 withdrawals, 1 A06 conditional-not-fit record, 4 active-set
rule registrations.

## Contradictions found

1. **Node contract vs write scope** (reported, not silently reconciled): acceptance criteria require
   registry appends; the write scope excludes the registry. Resolved by the payload-for-coordinator
   protocol above, which satisfies "single writer" and "existing 41 byte-identical" simultaneously.
2. **D026 arm count vs A06's own deadline**: D026 counted "23 fit-eligible" with A06 conditional; at
   this freeze the receipt has measurably not landed, so A06's own frozen clause executes — card
   frozen (23 cards), arm not fit (22 fitted). This is the clause running as designed, recorded
   plainly so nobody reads 23-vs-22 as drift.
3. **P33 A09/A10 "fold-locally fit/selected" vs the frozen fitted-element Holm semantics** (P34
   MULT B-4): resolved by striking the selection glosses under regime (i); recorded in both cards.
4. All P33-internal and document-vs-bytes contradictions found by P34 (A08 constraint, A16/A17/A21
   definedness, A22 parenthetical, A11 three-clause conflict, kill-alpha texts, V2 retirement tension)
   are closed in the cards with the original texts struck-and-preserved, per standing rule 1.

## What I could NOT establish

* Whether the coordinator's append will occur before P36 dispatch — outside this node; the freeze
  payload is self-contained either way.
* Anything requiring fitted quantities (A12/A13 active-set counts, A04/A09-style near-affinity numbers
  for d_t, IRLS behaviour on draws) — P36 scope by design; the specs governing them are frozen here.
* Whether a preseason-published schedule artifact exists OUTSIDE the read scope (A06 path (a)) — only
  its in-scope absence is measured.

## Stop conditions

None tripped. Every closure is arm-level or a specification completion inside D026's rulings; the
primary target, D007 K0 map, D006 inference scaffold, universe, cutoff-valid set and leakage status
stand untouched. Two recorded HALT triggers survive for the future, not exercised here: (a) any
reading of the V2 retirement as binding estimation machinery; (b) any attempt to answer A01's
free-slope question, which requires a USER-gated guard revision.
