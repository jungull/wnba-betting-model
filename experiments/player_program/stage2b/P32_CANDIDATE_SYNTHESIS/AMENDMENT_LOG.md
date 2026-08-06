# P32_CANDIDATE_SYNTHESIS — AMENDMENT LOG (adjudication D021)

Applied by the amendment agent, 2026-08-06, against SPEC.json frozen sha256
`f71fc4451e6f68b458229139ef733b57c0c40696a46e9e63b2a16cf99abdb757` (verified byte-for-byte before
any edit; MATCH). Post-amendment sha256 is recorded at the bottom. One entry per numbered edict
in the D021 dispatch. Files touched: `SPEC.json` and this log only. REPORT.md and the two
REVIEW_* files were not modified. No fit was performed; SEALED_RESULTS was not read.

---

## Edict 1 — A04.notes arm-id correction (A08 → A09) — APPLIED
**Demanded by:** Review A (REVIEW_IDENTIFIABILITY_K0.md) Finding F1, Severity B.
**Change:** every occurrence of arm-id `A08` in A04.notes replaced with `A09`, so the P25
near-affinity collapse/withdrawal rule targets F08/A09 (evidence_depth_adaptive_shrinkage),
matching A09.notes which was already correct. Family id `F08` untouched.
**Count note, recorded for exactness:** the edict (following Review A's phrasing) says "all three
occurrences"; the frozen text contained FIVE literal occurrences of `A08` in A04.notes
("(A08) flagged", "(A08, new construction)", "A08's rebuilt deviation", "A08 collapses",
"per A08's own declared failure mode"). The edict's operative instruction — replace the arm-id in
ALL occurrences so the rule targets F08/A09 — was applied to every occurrence; all five are now
`A09`, zero `A08` remain in A04.notes. This is not an approximation of the edict; the "three" was
an under-count in the review's citation, and applying it to only three of five would have left the
self-contradiction the edict exists to remove.

## Edict 2 — A02.notes arm-id correction (A14 → A16) — APPLIED
**Demanded by:** Review A Finding F2, Severity C (folded into Review A required change 1).
**Change:** both occurrences of `A14` in A02's residual-momentum distinctness note replaced with
`A16` ("Mechanistically distinct from A16 (residual momentum)... A16 builds a new lagged-residual
signal."). A14 is the expansion intercept decay (F11); the residual-momentum arm is A16 (F13).

## Edict 3 — A04 kernel basis STRUCK from the choice set — APPLIED
**Demanded by:** Review A Finding F3, Severity B; adjudicated at D021 to option (b) of F3's fix
(strike, do not basis-match).
**Change (three coordinated edits inside A04):**
- `hyperparameters.grid_or_choice_set.depth_response_basis`: element
  `"kernel 1/(1 + depth/h) with h = 5 (the CF-H2 frozen value)"` REMOVED; the binary tier basis is
  the sole remaining element. The hyperparameters note now records the D021 strike.
- `features[0].construction`: the descriptor "or bounded kernel 1/(1 + depth/h) (CF-H2 form)"
  REMOVED (it described the struck choice-set element), replaced with a pointer to the strike note.
- `notes`: appended the required record — the kernel basis was struck at adjudication (D021)
  because its declared null was not basis-matched (the null carries the binary tier main effect and
  the global slope only, so a kernel-basis treatment would own lower-order structure the null lacks
  — the S4 confound pattern); the kernel formulation remains preserved in the R3/D1a record.
- Per the edict, NO kernel main effect was added to any null; A04's k0_matched text is unchanged.

## Edict 4 — collapse_rule_A03_A07 added to A03 and A07 — APPLIED
**Demanded by:** Review A Finding F4, Severity B.
**Change:** a new field `collapse_rule_A03_A07` added to BOTH arms with mirrored text: if at
preregistration the two constructions (indicator threshold on pace_evidence_depth for A03;
exp(-n_i/5) evidence decay for A07) are found near-affine on the training universe under the P25
procedure, the pair collapses to ONE arm chosen by the S7-adjudicated tiebreak, the other is
withdrawn as a design decision, and only one multiplicity budget is charged. The rule is named as
mirroring the existing A04/A09 rule.

## Edict 5 — enumeration_obligation added to A03, A06, A08, A09, A10, A11, A16 — APPLIED
**Demanded by:** Review A Finding F5, Severity B.
**Change:** each of the seven arms now carries an explicit `enumeration_obligation` field: the
finite candidate elements MUST be fixed at preregistration (P33) before any fit, each element is
charged to the declared family multiplicity budget, and the word "small" is not a specification.
The word "small" deleted where it stood in as a spec:
- A03 grid: "preregistered single value or small grid" → "preregistered single value or grid".
- A08 grid: "small preregistered value or grid" → "preregistered value or grid".
(No other grid/choice-set cell contained "small"; remaining "smallest training fold" phrasings are
measurements, not specifications, and were left alone.)
A06 additionally: the monotone transform class is BOUNDED — the preregistration must enumerate the
exact finite set of transforms considered. A16's obligation additionally records that the ONE
preregistered k value is named nowhere in any source or the SPEC and must be fixed at P33.

## Edict 6 — frozen inference specification identified; scale convention NOT invented; inference_spec_gap recorded — APPLIED (gap path)
**Demanded by:** Review A Finding F6, Severity B.
**How the specification was identified (recorded per the edict):**
1. DECISION_LEDGER.jsonl entry `D006_FOLD_COUNT_IS_FIVE` rules that the implementation
   `possession_features.chronological_folds` governs the fold structure and that the packet prose
   DESCRIBES that function; RESEARCH_CONTRACT_V1.md's precedence line ("where the contract and a
   shared implementation appear to disagree ... the IMPLEMENTATION governs") is the cited authority.
2. `stage2a/CORRECTION_ADDENDUM.json` names "PHASE0A_RESOLUTION.md section 3 for the full inference
   specification"; `stage2a/build_evidence_packet_v2.py` declares the V2 packet carries "the
   accepted game-cluster inference specification"; EVIDENCE_PACKET_V3.json (`inference` block)
   carries that specification forward with the D006 five folds enumerated and
   `supersedes_for_candidate_selection` for this synthesis wave.
3. PROGRAM_STATE.json names no competing inference document (its shared_contracts list carries the
   gates, and possession_features.py is the only receipted feature producer);
   I10's clustered_inference.py was examined and EXCLUDED — its own header states "adopting these
   utilities as the program's inference method is a decision this node does not make".
**Identification written into shared_estimator_convention:** the `inference` block of
`experiments/player_program/stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json`, sha256
`95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75` (identical to the SPEC's own
pinned input hash), with its governing implementation `experiments/player_program/possession_features.py`
(sha256 `d44cca3828476e1c38b1e310d5ef9974e46afa68df8596cb22fdd24e2670d105`) and its lineage
`experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json` (sha256
`3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c`) ←
`experiments/player_program/stage2a/PHASE0A_RESOLUTION.md` section 3 (sha256
`137b7267d0a364320c0ef2121151da1652ae6454a18e96dd02039097b51a4b91`).
**Gap, stated plainly:** that specification fixes folds, clustering, resampling, row weighting and
the estimand, but NONE of the located documents fixes a GLM link or the scale on which
centered-offset treatment columns (A01/A02/A04) enter. Per the edict no scale convention was
invented: `INFERENCE_SPEC_GAP` is recorded inside shared_estimator_convention as a NAMED P33
OBLIGATION — fixing the link and the centered-offset treatment scale from the receipted estimator
convention before any fit.

## Edict 7 — A06 marked INADMISSIBLE_UNTIL_RECEIPTED — APPLIED
**Demanded by:** Review B (REVIEW_CUTOFF_FOLD_DEDUP.md) Finding F-1, Severity A.
**Change:** new `admissibility` field on A06: INADMISSIBLE_UNTIL_RECEIPTED, with the two repair
paths named verbatim — (a) a preseason-published schedule artifact receipted under the P23
franchise-continuity/receipt discipline establishing scheduled season endpoints as pre-cutoff
facts, or (b) redefinition of the phase/index denominator from past-only schedule facts. States
that the current S8 game_date citation covers only the per-game date and does not adjudicate
scheduled-season-length; receipt acquisition flagged as parallel data-lane work (D021).

## Edict 8 — A02 marked INADMISSIBLE_UNTIL_SHOWN — APPLIED
**Demanded by:** Review B Finding F-2, Severity B.
**Change:** new `admissibility` field on A02: preregistration must establish from receipts that
own_est/opp_est lie on the D009 standard-(a) receipted Stage 1B path, and must pin the relationship
of (own_est − opp_est) to the already-admitted pace_gap feature, including its interaction with
A15 null accounting.

## Edict 9 — P23 PHO/PHX receipt precondition extended uniformly — APPLIED
**Demanded by:** Review B Finding F-3, Severity B.
**Change:** the P23 franchise-continuity precondition (same wording as the existing A11
declaration: "franchise continuity across the PHO/PHX rebrand must be receipted by the P23 merge
guard for ANY cross-season history feature — P23 merge-guard receipts required at preregistration")
appended to the notes of all nine arms whose lag window can span a season boundary: A08, A09, A10,
A16, A17, A19, A21, A22, A24 — in addition to A11/A12/A13/A14 which already carried it. The
`rejection_category_scan.unsafe_fan_out_feature` line updated to record the uniform D021 extension
with the nine arm ids, so the scan and the arms agree.

## Edict 10 — A14 single-active-fold preregistration obligations — APPLIED
**Demanded by:** Review B Finding F-4, Severity B.
**Change:** new `preregistration_obligation` field on A14: the preregistration MUST (a) state in
advance what inference a single-active-fold result licenses, and (b) restate the kill conditions so
they are decidable when exactly one training fold contains expansion team-games — the realistic
case under the arm's own 2022+ first-season definition.

## Edict 11 — R5 rationale amended; disagreement preserved — APPLIED
**Demanded by:** Review B Finding F-5, Severity B; Review A Finding F9, Severity C; D021
adjudication of the label dispute.
**Change:** appended to R5.detail (original text left in place so the overstatement is visible
rather than erased): AI-H4 names a genuine physiological fatigue-after-OT confound — an
unproposed-but-legitimate primary-target mechanism — and the "ZERO by its own construction"
phrasing overstated the source. The rejection outcome, category, and preserved diagnostic
recommendation stand unchanged. D021 preserved-disagreement note appended: Review A reads the
category label as stretched for an audit arm already outside the promotion universe; Review B
keeps the label with the amended rationale.

## Edict 12 — preserved disagreement D9 added (OT-handling divergence) — APPLIED
**Demanded by:** Review A Finding F8, Severity C; Review B Finding F-7, Severity C.
**Change:** new entry D9 in preserved_disagreements: A12 rescales prior-game OT to
regulation-equivalent, A16 normalizes by regulation-equivalent duration, A26 deliberately uses raw
counts under an unmeasured symmetric-cancellation assertion; preregistration may NOT silently
harmonize the three. Noted beside it (per Review A) that this is a fifth frozen-convention
divergence of the D6 kind.

## Edict 13 — ledger corrections (a)–(e) — APPLIED
**Demanded by:** Review B Finding F-6 (a)(b), Severity C; Review B F-8, Severity C; Review A
Finding F10, Severity C; Review A Finding F7, Severity C.
**Changes:**
- (a) A23 hyperparameters note and D7: cap 7 corrected to "appeared as an example
  (e.g. min(rest,7)) in AI-H2, not a frozen constant"; OM-H4's cap 4 and CL-H5's cap 10 remain
  recorded as source-frozen. Both places marked "[corrected at D021]".
- (b) A23 grid_or_choice_set gains the explicit named choice `prior_game_definition`:
  ["previous SCHEDULED same-season game (AI-H2)", "most recent COMPLETED same-season game
  (OM-H4)"] — the divergence the merged formula had silently glued together.
- (c) A23 features construction softened: "satisfies even the strict D009 standard (b) trivially"
  → "cutoff-valid by construction conditional on the P23-receipted game_date join (game_date is
  joined from a retrospective bulk scrape with declared revision risk)".
- (d) D8 phrasing corrected: GENERATION_ORDER records four sources RECOVERED their isolation
  directories and implies isolation copies existed for the two thin sources as well.
- (e) A23.notes (previously empty) now carries the P33 recommendation to pair the two
  source-consistent bundles (cap 7 + previous-scheduled opener rule; cap 4-or-merged +
  most-recent-completed) rather than cross-producting choice sets no source proposed.

## Edict 14 — post-edit validation — APPLIED
`python -c "import json; json.load(open('SPEC.json'))"`-equivalent run (UTF-8): **parses OK**.
Recounted from the parsed bytes, not from the report: **20 families, 26 arms, 5 rejections**
(26 + 5 = 31 = candidate union, unchanged). Arm ids remain unique; no arm was added, removed,
renamed, or re-familied by any amendment. All coverage checks (enumeration obligations on exactly
the seven named arms, collapse rule on exactly A03/A07, admissibility fields on exactly A02/A06,
preregistration obligation on exactly A14, preconditions on all nine named arms, D9 present,
D7/D8/R5/A23 corrections in place) verified by script over the parsed JSON.

---

## Blocked amendments
None. All fourteen edicts applied. The only deviations from literal edict text, both recorded
above rather than silently absorbed: (1) edict 1's "three occurrences" was five in the frozen
bytes — all five replaced; (2) edict 6 resolved to the named `inference_spec_gap` path the edict
itself prescribes for the case the located specification does not fix the link/scale — which it
does not.

## Hashes
- SPEC.json before amendments: `f71fc4451e6f68b458229139ef733b57c0c40696a46e9e63b2a16cf99abdb757` (verified MATCH before first edit)
- SPEC.json after amendments: `1dc25981ed14be0ef59c994a47a99970d790b644d8cdce354c617f9198c2138c`
