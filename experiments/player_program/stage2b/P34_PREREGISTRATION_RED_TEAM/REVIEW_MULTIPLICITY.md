# P34 RED TEAM — REVIEW_MULTIPLICITY

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

**Reviewer dimension:** multiplicity (family partition, dual-Holm well-definedness, double funding, enumeration budgets, alpha accounting).
**Verdict: ACCEPT_WITH_REQUIRED_CHANGES.** No Severity A finding. Seven Severity B findings must be closed at or before the P35 task-card freeze.

**Stop conditions: NOT tripped.** Nothing below changes the primary target, the K0 structure, the fold/cluster/bootstrap inference structure, the candidate universe, the cutoff-valid feature set, or any leakage status. P32's own D2 record scopes the multiplicity partition as affecting "family-wise error budgeting, not fold/cluster inference structure"; every required change here is a budgeting/partition repair inside that scope.

**Blindness:** I read no other P34 reviewer file. At the time of writing, this file is the only content I have placed in `P34_PREREGISTRATION_RED_TEAM/`, and I inspected no other file in that directory.

---

## 1. Inputs verified

`Get-FileHash -Algorithm SHA256` (PowerShell), all four match the dispatch:

| file | sha256 |
|---|---|
| P33_PREREGISTRATION_DRAFT/SPEC.json | 066b2a04...d347d093 |
| P33_PREREGISTRATION_DRAFT/REPORT.md | 6d945b86...81248ab (full: 6d945b8663323526ba29fc74cdf963c800ff26d12bac846e12ef69d1681248ab) |
| P32_CANDIDATE_SYNTHESIS/SPEC.json | 1dc25981...7198c2138c |
| P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json | 95d2412c...50875e75 |

Also read: RESEARCH_CONTRACT_V1.md, P32 ADJUDICATION.md, orchestration/DECISION_LEDGER.jsonl (D021 ruling), HYPOTHESES_timeseries_shrinkage.md, HYPOTHESES_adversarial_identifiability.md, the P34 node prompt. No SEALED_RESULTS content, no performance data, nothing fitted.

## 2. What I measured

All structural numbers below come from `p34_multiplicity_checks.py` / `p34_multiplicity_checks2.py` (scratchpad; parse the frozen P33/P32 SPEC bytes only — no target values, no fits). Key outputs:

* 26 arms; each appears in **exactly one** multiplicity family in the families block; member short-ids cover all 26.
* Per-arm element charge equals max(enumerated grid size, 1) for **all 26 arms** — zero mismatches (A03:1, A04:1, A06:2, A08:2, A09:3, A10:2, A11:3, A16:1, A23:2; all zero-grid arms charged 1).
* Family sums match declared budgets exactly: CAL 5+2c, timeseries 10, COLDSTART 5, lagged_pace 1, LAGGED_TEMPO_MIX 2, EVIDENCE_QUALITY 1, PERSONNEL 1, SCHEDULE_FATIGUE 1, schedule_context 3, OPPONENT_F1 3. Total 32 unconditional + 2 conditional elements over 10 families.
* Mechanism families (P32 `family_id`, defined there as "one falsifiable mechanism per family") split across two multiplicity families: **F06** (CAL / COLDSTART), **F10** (timeseries / COLDSTART), **F14** (LAGGED_TEMPO_MIX / OPPONENT_F1), **F15** (LAGGED_TEMPO_MIX / OPPONENT_F1), **F18** (schedule_context / SCHEDULE_FATIGUE).
* P32 arms carrying CONFLICTING or CONFLICTING-ADJACENT multiplicity declarations: A06, A07, A11, A12, A13, A17, A18, A19, A20, A23, A24, A25. P33's dual-Holm covers only A06, A07, A11, A12, A13 (the D2/D5 subset). **Seven conflicting-declared arms get no dual check.**
* `temporal_drift_family` appears in **no** entry of the P33 families list; its only would-be member is A06.
* Six arms (A01–A06) carry the kill phrase "family-corrected ... = 0 not rejected" while `inference.coefficient_inference` freezes "Kill conditions are evaluated UNCORRECTED".
* A19's `k0_matched` (the citation target for the LAGGED_TEMPO_MIX weaker-member drop rule) contains no occurrence of "drop" or "weaker".
* Bootstrap granularity: B = 10,000 → min two-sided p ≈ 2.0e-4; worst realizable Holm first threshold across primary and alternate partitions = 0.05/12 ≈ 4.17e-3. **Granularity adequate everywhere.**
* The only "program-wide" string in the P33 SPEC concerns the offset convention. There is **no program-wide alpha statement** and no cross-family promotion/both-pass rule anywhere in the frozen bytes. 10 families at family-wise 0.05: additive bound 0.50, independence approximation ≈ 0.40 that at least one family funds a false arm under the global null.
* Source-text checks: HYPOTHESES_timeseries_shrinkage.md line 183 — the entire source constraint on A08's K is "(K small, preregistered ...)"; its family notes ("every grid point of kappa (TS1), lambda (TS2), rho (TS3), K (TS4) is counted inside the family budget") support the every-element-is-a-hypothesis reading. HYPOTHESES_adversarial_identifiability.md lines 84–86: A16's family accounting is source-blessed as "one preregistered k is fitted, the family carries the accounting".

## 3. Findings

### B-1. The provenance rule, applied per-arm to family-level disputes, manufactures a partition no source proposed and double-funds three mechanism families with no compensating check

F14 (A17 vs A18), F15 (A19 vs A20) and F18 (A23 vs A24) are each ONE P32-adjudicated falsifiable mechanism, and each is charged to TWO multiplicity families with independent 0.05 budgets. The F18 case is the sharpest: P32 declared the rest mechanism CONFLICTING-ADJACENT across three source readings (schedule_context per AI-H2, OPPONENT_MECHANISM_F1 per OM-H4, SCHEDULE_FATIGUE per CL-H5). Under **every one** of those three readings the two rest arms co-locate in a single family with denominator ≥ 3. The frozen configuration — A23 in schedule_context (Holm over 3), A24 alone in SCHEDULE_FATIGUE at **uncorrected alpha 0.05** — is the one configuration that appears in no source's mechanism-level reading, and it is weakly more lenient than all three. That inverts the RESEARCH_CONTRACT_V1 stricter-governs principle exactly where a dispute exists. The identical structure holds for F14 and F15 (each source reading co-locates the pair; the frozen partition separates them, and the LAGGED_TEMPO_MIX member gets denominator 2 while its same-mechanism sibling sits in OPPONENT_F1 at denominator 3).

**Required change:** at P35 either (i) co-locate each split mechanism family (F14, F15, F18) in one multiplicity family per stricter-governs, or (ii) extend the dual-Holm stricter-governs discipline to A17, A18, A19, A20, A23, A24, A25 with pinned alternate compositions, or (iii) record an explicit, argued acceptance that the multiplicity unit is the source lineage and not the mechanism — in which case the P32 "one falsifiable mechanism per family" semantics must be expressly disclaimed for multiplicity purposes and the mechanism-level funding rate acknowledged as additive.

### B-2. D2's three-way dispute was silently reduced to two-way, and A06's dual check as frozen is mathematically vacuous

P32 D2 records THREE candidate families for the F06 within-season-drift mechanism: CALIBRATION_CONTROL (CC-H5), temporal_drift_family (AI-H5), COLDSTART_FALLBACK (CF-H3). P33 checks A06 only under CAL (primary) and temporal_drift (alternate). As constituted, temporal_drift_family contains only A06's own 2 elements — a strict subset of the elements in the CAL run. By the closed-testing structure of Holm, rejection of an element in a superset family implies rejection in any subset family containing it; the subset run can never be the binding one, so "survive under BOTH" reduces to the CAL check alone. The dual check adds nothing, and the one alternate that could bind — A06 charged into COLDSTART_FALLBACK (CF-H3's reading, making COLDSTART 7 elements) — is omitted. The SPEC's claim "Neither reading is erased" is therefore false in operation for D2's third reading. (Symmetric question, unaddressed in the bytes: whether A07 owes a temporal_drift-side check under AI-H5's reading of the shared F06 mechanism.)

**Required change:** add the A06-under-COLDSTART configuration to the dual (now triple) check, or record explicitly why CF-H3's reading binds A07 only; state in the frozen record that the temporal_drift alternate is subset-vacuous rather than presenting it as a live check.

### B-3. Dual-Holm alternate-family compositions are unpinned, and stricter-governs stops at the disputed arm

(a) *Compositions.* "Survive Holm under BOTH candidate partitions" is only computable once the alternate family's full membership is fixed. Unstated: whether all other disputed arms are held at their primary assignments during a given arm's alternate run (D5 moves A11 and A12/A13 in opposite directions between the same two families — the four resulting configurations give different Holm outcomes); whether A06's conditional elements sit in CAL during A07's CAL-alternate run if the A06 receipt lands. The natural reading (hold-others-at-primary; conditional elements per their P35 admissibility) is defensible but is nowhere frozen, and Holm outcomes differ across readings.

(b) *Asymmetry.* The stricter-governs obligation binds only the disputed arm. If the alternate reading is true — A07 genuinely belongs to CAL (family of 8), A12/A13 genuinely belong to timeseries (family of 12) — then every NON-disputed member of the enlarged family (A01–A05; A08–A10) is under-corrected in the frozen procedure, which never re-runs them at the larger denominator. A family-size dispute burdens the newcomer and never the incumbents. This is the anti-conservative direction and it is exactly the kind of partition uncertainty stricter-governs exists for.

**Required change:** P35 must enumerate, per disputed arm, the exact element sets of both (or all three) Holm runs; and must either extend the survive-both requirement to every member of any family whose composition is disputed, or record acceptance of the asymmetry with its direction stated.

### B-4. Element semantics are contradictory: fitted-grid Holm vs fold-local training selection cannot both hold

The partition rule defines the correction as "Holm within family over the family's fitted elements (arm x enumerated-grid-element)" — i.e., each grid element is a hypothesis with its own pooled out-of-fold p-value (the TS source's "every grid point ... counted inside the family budget" supports this). But A09's record says kappa is "fold-locally fit on training rows only" and A10's says lambda is "fold-locally selected on training rows". Under fold-local selection the element identity varies by fold, the pooled arm is a mixture of grid elements, and per-element pooled p-values do not exist — the Holm procedure as defined has no inputs. The two readings produce different denominatorial behavior and different tests. Related gaps: A06's formula joins its two enumerated bases with "OR" (are both fitted?); and if two or more elements of one arm survive Holm (e.g., both A08 windows), no preregistered rule selects which element is the promotable candidate — a post-hoc choice at exactly the moment the preregistration exists to prevent.

**Required change:** per grid-carrying arm (A03 trivially, A06, A08, A09, A10, A11, A23), P35 must state which of the two regimes governs: (i) every element fitted end-to-end as its own variant, one pooled OOF p-value per element, Holm over all family elements; or (ii) training-time selection with a single arm-level p-value and the unselected elements charged at p = 1 in the Holm ordering (or an equivalent explicit charging rule). Add the multi-survivor promotion-selection rule.

### B-5. Kill-condition alpha accounting is self-contradictory, and its "conservative direction" rationale is backwards for failure-to-reject kills

`inference.coefficient_inference` freezes: "Kill conditions are evaluated UNCORRECTED (... uncorrected kills are the conservative direction)." Six arm records (A01–A06) freeze kills of the form "**family-corrected** delta = 0 not rejected (95% ... interval covers 0 in every fold)". Both cannot be implemented. Further, the rationale is only correct for rejection-type kills (e.g., opposite-sign rejection). For failure-to-reject kills, the corrected criterion (wider intervals) fires MORE kills; evaluating them uncorrected fires FEWER — the anti-conservative direction. The damage is bounded (a kill-survivor must still pass the Holm-corrected primary gate to promote), but the frozen bytes contradict each other about which alpha the kill machinery uses.

**Required change:** strike one text. Either delete "family-corrected" from the six kill conditions (making the uncorrected 95%-interval operationalization govern), or amend the inference block; state the direction consequence either way.

### B-6. Two family-level procedures are invoked but specified nowhere in the frozen bytes

(a) LAGGED_TEMPO_MIX: the families block cites a "preregistered weaker-member drop rule (A19.k0_matched declaration)". Measured: A19's k0_matched contains no drop rule — no definition of "weaker", no statistic, no stage, no statement of the survivor's alpha after dropping (Holm over 2 → survivor at 0.025, or uncorrected 0.05 after selection — the difference is exactly a max-selection multiplicity charge). "Family scored jointly" also sits unreconciled beside each member's own per-arm primary gate. (b) A13 fixed-sequence: "confirmatory only if A12's joint treatment rejects" — rejection at which level (uncorrected, COLDSTART-Holm, or the dual-partition stricter result) is unstated, as is whether A13's element stays in the COLDSTART denominator when its result is exploratory (the members table says its slot is always occupied; the text should say so in the procedure).

**Required change:** write both procedures into the P35 task cards as decidable rules; a citation to a declaration that does not contain the rule is a defect of the frozen record.

### B-7. No both-pass adjudication exists, and no program-wide alpha statement bounds the 10-family design

Promotion is defined arm-by-arm. Nothing in the frozen record adjudicates the case where correlated arms in DIFFERENT families both pass. Direct answer to the dispatched question on A03/A07: **the no-collapse result is not double funding under the program's own frozen semantics** — F03 and F06 are dedup-adjudicated distinct mechanisms, the D021 collapse rule was executed honestly pre-fit (max training-fold R2 = 0.7134 and max |spearman| = 0.5141, nowhere near 0.998001 / 0.999), and A07's null owns the depth mains. But the collapse criterion is an *identifiability* threshold, not a mechanism-identity test: at R2 ≈ 0.71 in exactly the fold where both cold-start claims live, and with A03's null carrying NO depth information, the two tests substantially overlap on the same underlying signal while drawing on two separate family budgets — the funding rate for "some early-evidence level correction" under the global null is approximately the sum of the two family alphas, and if both pass, the frozen record licenses promoting both even though each was validated against a null lacking the other's term. The same both-pass exposure holds for the B-1 pairs (A17/A18, A19/A20, A23/A24). Program-wide: 10 families at family-wise 0.05 imply an additive bound of 0.50 (independence approx ≈ 0.40) on at least-one-false-family-funding; that may be an acceptable, conventional design — but it is nowhere stated, and a later report could imply program-wide control that was never provided.

**Required change:** one preregistered paragraph at P35: (i) the both-pass rule for cross-family correlated survivors (e.g., joint nested re-test of any two passing arms whose treatments share a training-fold R2 above a stated bound, or a portfolio-selection rule); (ii) an explicit declaration that error control is per-family Holm at 0.05 and that no program-wide FWER claim is made or may later be cited.

### C-1. A03's "no other element is defensible" is overstated (record)

t = 3 is genuinely anchored (incumbent switching boundary, measured 2982/2982; depth histogram {0, 3..10} makes t ∈ {0,1,2} a single unsupported stratum). But the uniqueness claim is rhetoric: the producer's frozen WINDOW_K = 10 is accepted elsewhere in this same document as a "frozen evidence" anchor (A09's kappa grid), so a depth threshold at the window cap would be defensible by the identical argument form. The charge (1 element, pre-fit, feature-only) is honest; only the exclusivity claim is wrong. No budget change required.

### C-2. A08's {20, 80} and A16's k = 5 are constructed justifications, honestly charged (record)

Source text for A08 is "(K small, preregistered)" and nothing else (HYPOTHESES_timeseries_shrinkage.md:183) — the specific values and the "two named drift horizons" narrative are P33 inventions. A16's source names no k and expressly delegates ("one preregistered k is fitted, the family carries the accounting", HYPOTHESES_adversarial_identifiability.md:84–86). In both cases the accounting is sound (every element charged, frozen pre-fit, no performance data available to the chooser); the "ENUMERATION OBLIGATION DISCHARGED [from source]" framing overstates the derivation but not the count. Record; no change required beyond honest labeling if P35 rewords.

### C-3. The quasi-Poisson freeze is multiplicity-neutral only because it is global and irrevocable (record)

Under this reviewer's lens the un-receipted response-family freeze is acceptable: it is a single program-wide convention fixed before any fit, adds no searched dimension, and no likelihood-based SE is ever consumed — so it charges nothing and games nothing. The hazard is downstream: any per-arm deviation at P36 (e.g., a Gaussian refit for a convergence-troubled arm) would be an uncharged degree of freedom. The seed manifest already voids stochastic fitting; recommend the P35 cards add the parallel clause that any response-family or objective deviation voids the arm.

### C-4. Verified sound (positives, for the record)

* Family budget arithmetic exact: 26 arms, each in exactly one family; per-arm charge = max(grid, 1) for all 26; family sums equal declared budgets; 32 + 2-conditional elements. Nothing missing.
* Alpha accounting at family level IS stated before any fit (Holm, 0.05 family-wise, budgets enumerated in the frozen draft).
* A14's retained Holm slot despite promotion-ineligibility is the conservative choice and prevents quiet denominator shrinkage.
* Conditional-element timing (A06 enters/leaves the denominator at P35 freeze, pre-fit) is well-defined and not outcome-dependent.
* Bootstrap resolution (min two-sided p ≈ 2.0e-4 at B = 10,000) clears the smallest realizable Holm threshold (0.05/12 ≈ 4.2e-3) with two orders of margin, on primary and alternate partitions alike.
* A23's refusal of the 8-cell cross-product, with both source-consistent bundles charged, is exactly right; the "cap 4-or-merged" ambiguity was resolved to the only source-frozen constant and the resolution is honestly annotated.

## 4. What I could not establish

* Whether the D2/D5 "candidate partitions" were intended by their sources as global partitions or per-arm marginal moves: the source HYPOTHESES files declare families per-hypothesis, and neither P32 nor P33 defines the joint object; this is why B-3(a) demands pinning rather than asserting a right answer.
* Whether any downstream node (P37+) already carries a both-pass/portfolio rule that would discharge B-7(i): nothing in this node's inputs does, and I did not read beyond the declared read scope.
* Anything requiring fitted quantities (all findings above are structural, from frozen bytes and feature-free arithmetic).

## 5. Verdict

**ACCEPT_WITH_REQUIRED_CHANGES.** The budget arithmetic is exact, the family-level alpha is stated pre-fit, and the enumeration charges are honest. But the partition itself is the weak joint: three mechanism families are double-funded with no compensating check (B-1), one leg of the D2 dual check is vacuous and a third reading was erased (B-2), the dual-Holm procedure is not yet a computable object (B-3, B-4), the kill-condition alpha text is self-contradictory (B-5), two family procedures are cited into a void (B-6), and the both-pass / program-wide accounting is silent (B-7). All seven are closable at P35 without touching any stop-condition-protected structure.
