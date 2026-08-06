# P37 ADJUDICATION — DRAFT FOR COORDINATOR SIGN-OFF

**Status: DRAFT. Compiled and PROPOSED by the P37 adjudication compiler, which decides nothing.
The coordinator ratifies, amends, or rejects each proposal; the ratified ruling is appended to
`orchestration/DECISION_LEDGER.jsonl` (pattern: `D026_P34_ADJUDICATION`) and the coordinator
materializes `REPORT.md` after ratification. Machine-readable register: `SPEC.json` beside this
file.**

---

## Question (D026 form)

All three P37 implementation auditors returned their slices with the shared verdict *the code is
substantially the preregistered code*: runner slice clean (14/14 re-run bit-identical, all four
RAISED ambiguities ruled or routed), arms A02–A13 with **one Severity A** (A08) and five Severity
B, arms A14–A26 with five Severity B including one card-defect that makes A24 **unrunnable at P38
as implemented**. Eleven Severity B in total (one conditional), ~20 Severity C, zero stop
conditions raised by any auditor. Halt, or close at arm/mandate level?

## Proposed ruling

**NO HALT; CLOSE AT ARM/MANDATE LEVEL**, per the D026 pattern: the one Severity A gets a
remediation node already directed by the coordinator handoff (remediation-in-flight, §3); the one
unrunnable arm gets a pre-P38 disposition by registry-appended amendment with the auditor's two
options presented verbatim (§4); the fold-policy naming goes to the P38 executor with both
recorded facts and the frozen-precedence analysis (§5); **every Severity B is a mandatory item**
— a named P38-executor mandate entry or an arm-level pin, none optional, none silently absorbable
(§6); every disagreement is preserved in writing, never averaged (§8).

Authority: GRAPH_POLICY §5 (Severity B failures spawn remediation nodes; the coordinator decides
without asking when remediating a confirmed implementation defect, or when advancing an
experiment whose frozen preregistration and implementation audits pass), §6 (no USER_REQUIRED
trigger is met — see the six-dimension analysis below), §11 (a blocker blocks descendants in its
lane, not independent work); frozen-bytes-govern (§1); D006 and D026 as controlling precedents.

---

## 1. No-halt analysis against the six frozen dimensions

The program's stop conditions trip only if a finding would change one of the six frozen
dimensions. Each auditor ran this assessment independently and reported no trip; the compiled
analysis:

| frozen dimension | finding pressure | analysis |
|---|---|---|
| **Primary target** | none | No finding in any slice touches the estimand. |
| **K0 structure** | A2-A1 (A08) | Threatened **as implemented** in one arm only: A08's rank-strict clock makes its d_t diverge from the K4 shared column. The K0 structure **as specified** is untouched — the remedy is a code correction *toward* the frozen bytes (auditor 2's own stop-condition assessment, adopted verbatim). The parity run proves the zero-parameter nulls ARE the incumbent bitwise. |
| **Inference structure** | R-F1, fold-policy, p-value | R-F1 is a fail-closed implementation divergence remedied at the call site (can only wrongly kill, never wrongly promote). The fold-policy naming selects between readings **D006 already fixed** at five expanding folds — no new inference choice is being made. The p-value formula was completed while every agent was blinded, before any result existed — the epistemically acceptable direction, now frozen by condition EXEC-M3. |
| **Candidate universe** | A3-B3 (A24) | An arm-level disposition, exactly the D026 closure form (A01/A04/A19 there; 26 → 23 arms). No universe row, cluster, or fold changes. |
| **Cutoff-valid feature set** | clock family | Every clock finding (A3-B1/B4/B5, A2-B2) concerns past-facts-only quantities under **either** clock reading. Nothing enters or leaves the cutoff-valid set. |
| **Leakage status** | A2-A1 edge | Unchanged everywhere. The closest pressure is A2-A1's same-date window admission; auditor 2 records it as an identity failure whose fix *restores* the frozen leak-free wording, and auditor 3 records every B in its slice as past-facts-only with machinery symmetric arm/null. |

No USER_REQUIRED trigger fires: no estimand change, no gate weakened after an observed outcome
(everything here precedes unsealing and every agent remained blinded), no frozen canonical
artifact modified (the A08 fix is to an *implementation* file owned by P36, not a frozen
canonical path; the A24 amendment is registry-**appended**, the only permitted direction), no Arm
D contact, no known leakage accepted (A2-A1 is remediated, not accepted), no registry record
altered.

## 2. What the audits established (compiled)

- **Custody:** all three auditors independently re-measured every byte pin (P35 cards, P33, five
  guards, team_cities, both frozen real input artifacts) — all match. One transcription typo in
  the runner audit's *abbreviation* of the P35 hash (register finding CMP-1; re-measured from
  bytes by the compiler, verdict unaffected).
- **Tests:** runner 14/14 with a bit-identical end-to-end results digest to the P36 receipt; ten
  A02–A13 suites pass; 164/164 A14–A26 test functions pass; 21/21 row-parity spot checks pass
  (zero-parameter null MAE == incumbent MAE with exact float equality; null mu bitwise
  `exp(log_exposure)`; K0_FLAT records byte-identical across arms).
- **Blinding:** held fleet-wide; structural refusal verified positive and negative;
  `P38_UNSEALED` absent throughout all three audits.
- **Code identity:** runner VERIFIED (one B, F1); A02–A13: nine of ten arms conformant, A08 the
  Severity A; A14–A26: 10 of 12 card-exact, A20/A21 construction deviations, A23/A26 clock
  family, A24 card-exact against a defective card.

## 3. A08 — Severity A CONFIRMED; remediation IN FLIGHT

Finding A2-A1: `arms/A08/features.py` implements rank-strict "strictly earlier" where the frozen
pins (`d_t_league_mean_pin`, `a08_window_tie_break`) demand date-granular strictness; measured
divergence 156/240 rows on a tie-heavy fixture; K4 shared-null identity broken as implemented;
the module's own docstring states the rule its code does not implement; A08's suite never
exercises ties.

**Proposed disposition — remediation-in-flight note.** Remediation proceeds as its own node per
GRAPH_POLICY §2 ("remediation is a *new* node that declares the failure as its parent finding")
and was already directed by the coordinator handoff of 2026-08-06 ("A08 remediation node …
re-implement to the card (the card is right, the code is wrong)"). Scope pinned here so the node
cannot drift:

1. Re-implement `features.py` to date-granular strictness; `(game_date, game_id)` is a tie-break
   *within* the strictly-earlier-date set, never a redefinition of it. A09/A10/A11 are the
   in-fleet reference implementations (measured byte-identical to one another).
2. Add a tie-heavy (multiple-games-per-date) fixture to A08's suite — the one-game-per-day
   fixture is why 10/10 passed over the defect.
3. Re-verify K4: A08's d_t byte-identical to A09/A10's on the tie fixture.
4. Targeted re-audit by a context that implemented neither A08 nor the fix (GRAPH_POLICY §9
   rule 1: verification of a Severity A node never runs below the tier of the work it verifies).

**A08 is NOT FIT-ELIGIBLE and promotion-blocked until the remediation node passes.** Blocking
scope is the A08 lane only (§11); no other arm and no P38 scheduling for the rest of the fleet is
blocked. This is a code correction toward frozen bytes — not a preregistration change, not a
registry edit, no stop condition.

## 4. A24 — pre-P38 disposition required; options exactly as the auditor framed them

Finding A3-B3: the module **matches the card; the card is defective**. "Fallback: none needed" is
measured-false on three franchise debuts (team 1611661331's 2025 debut; 1611661327 and
1611661332's 2026 debuts — named in A14's own frozen card); rest is structurally undefined on the
debut rows and their opponents' rows (≥ 6 rows, including fold-4/5 TEST rows);
`build_design` raises `A24ConstructionFailure`. **A24 is unrunnable at P38 as implemented.** The
implementer's refusal to invent a substitution is correct under standing rules 1/7, and the
frozen-record contradiction (A24's card vs A14's card) is preserved as A3-X3.

**The auditor's disposition options, verbatim in structure:**

- **(a)** an adjudicated **fallback** for the franchise-debut rows, frozen before P38 by a
  **registry-appended amendment**; or
- **(b)** a **row/fold disposition** for the affected rows, frozen before P38 by a
  **registry-appended amendment**.

Constraints the auditor attached, carried unmodified: disposed **before** P38; by
registry-appended amendment, **not a silent P38 patch**; and because A24 is the preregistered
**LAG OPERATOR POSITIVE CONTROL** ("if the machinery cannot cleanly evaluate this arm, no
lagged-arm result should be trusted"), letting it fail at fit time would contaminate the
positive-control reading.

*Compiler note, not a decision:* the D026 A19 branch (withdrawal by an arm's own fail-closed
clause) is not among the auditor's framed options and interacts badly with the positive-control
role; if the coordinator contemplates it, that is a new question outside this draft. The choice
between (a) and (b), and the amendment text, are the coordinator's alone.

## 5. P27 fold-policy — both recorded facts, and the frozen-precedence analysis

The runner auditor ruled this **NEEDS-P38-EXECUTOR-DECISION** and measured both facts; both are
carried here in full, per the D026 preserved-disagreement discipline:

- **Fact (i)** — the S7 finding was stated under SEASON_BLOCK: "a tier indicator is IDENTICALLY
  ZERO in four of six chronological folds" (`stage2a/V2_STOP_CONDITION.json` line 134). Six
  **per-season blocks** exist, not six D006 folds.
- **Fact (ii)** — the D006 operative folds of the preregistration are literally the
  EXPANDING_PRIOR_SEASONS masks: `make_outer_training_folds(..., "EXPANDING_PRIOR_SEASONS")`
  emits fold ids `train_lt_<s>` — exactly the five frozen D006 fold ids — and the task cards'
  numeric active-set triggers ("≥ 10 training clusters …") are stated over D006 training folds.
- Arm-side corroboration: A05's P33-carried `train_lt_YYYY` fold naming and A11's
  `structurally_deactivated_folds() == ["train_lt_2022"]` (auditor 2); the parameter is consumed
  unchanged by all of A14–A26 (auditor 3); no conflict found in any of the 22 audited arms.

**Frozen-precedence analysis.** `D006_FOLD_COUNT_IS_FIVE` already ruled — under
RESEARCH_CONTRACT_V1 precedence (the implementation governs over ambiguous prose) and
GRAPH_POLICY §1 (frozen bytes govern) — that the operative inference folds are the **five
expanding folds** `train_lt_2022 … train_lt_2026` (2,982 rows / 1,491 clusters). Those five ids
are exactly what the guard's EXPANDING_PRIOR_SEASONS policy emits. **The D006 operative fold
masks therefore force the EXPANDING_PRIOR_SEASONS reading**: naming SEASON_BLOCK would have P27
certify estimability over six per-season blocks that nothing fits or scores — an audit of masks
with no operative existence. D006 also already disposed of fact (i)'s pull in the other
direction: the S7 measurement "is tabulated by SEASON across six seasons, not by fold across six
folds … must be restated in fold terms." Fact (i) is the *historical basis* of the support-floor
rule, not an operative mask.

**Proposal:** the coordinator ratifies the precedence analysis; the **P38 executor names
`EXPANDING_PRIOR_SEASONS` on the record before any real fit** (the naming lands in the P27
guard's own receipt, which already captures it). The shipped harness default (SEASON_BLOCK) must
never be relied on silently — the naming is explicit or the fit does not start. Ratify together
with **EXEC-M1** (§6): the named policy determines which internal folds P27 audits, and F1's
per-fold wrapper must honour those folds' verdicts individually.

## 6. Severity B → mandatory mandate items and pins (D026: "every Severity B is a mandatory item")

| item | source finding(s) | content |
|---|---|---|
| **EXEC-M1** | R-F1 | Call-site wrapper honouring P27 **per-fold** UNEVALUABLE verdicts symmetrically for arm and null; continue with remaining folds; implements A07's "≥ 2 folds" retirement arithmetic; never by editing the frozen guard; decided on the record before any real fit; ratified with §5. |
| **EXEC-M2** | RAISED 4.2 | Name `fold_policy = EXPANDING_PRIOR_SEASONS` on the record (§5); choice lands in the P27 receipt. |
| **EXEC-M3** | RAISED 4.3 condition | Bootstrap p-value formula consumed **byte-unchanged**; any change at/after unsealing is a preregistration deviation voiding affected comparisons. |
| **EXEC-M4** | A2-B2, A2-C14 | Pin how the 2,990-row contract schedule reaches A09/A10 `build_design` without entering fit rows (or constructor-bind history frames like their siblings), and that A08's caller-supplied `pace` is computed by the frozen formula. Passing the 2,982-row universe as-is silently yields the barred clock — prohibited. |
| **EXEC-M5** | A2-B5 | Bind the executor to invoke A03's `tier_symmetry_check` per fold, arm and null identically — the frozen "either tier" rule stays two-sided. |
| **EXEC-M6** | A3-B1, A3-B4, A3-B5, A3-X2 | **One fleet-wide adjudication** of the `n_clock_pin` scope (universal text vs K6 named-arm application), then the auditor's fork for A20/A23/A26: either pin the universe-row clock on the record, or require re-derivation on the possessions/contract clock (A24's constructor pattern is the in-fleet remedy). Compiler observation: the pin's own text ("the universe-row clock is barred") and frozen-bytes precedence read toward the contract-clock branch (implying remediation nodes for A20/A23; A26 bounded by its two verified exact mitigations); the other branch requires ruling the barred clock admissible on the record. Exposure re-measured at P38 either way. |
| **EXEC-M7** | R-F4 | Invoke `p26_check(bind=True)` at scoring time; `run_arm` does not exercise the bind path. |
| **PIN-A13** | A2-B3 | Proposed pin: the code's literal, card-supported reading (any negative per-fold point estimate fires the kill); the docstring's narrowing recorded as the rejected reading. Pinned before unsealing. |
| **PIN-A12** | A2-B4 | Proposed pin: the module's disclosed reading, with the β₁≈0 noise edge carried verbatim in the record (auditor: acceptable exactly on that condition); the predicted-direction alternative preserved as the road not taken. |
| **PIN-SIGN** | A2-B6 (+A2-C8) | Proposed pin: each arm's **as-implemented** sign-instability convention pinned explicitly per-arm before unsealing (A02/A03/A05 point-sign; A08/A11 interval-excludes-zero) — same epistemic direction as the p-value ruling; carrying both silently is prohibited. Alternative (harmonize to one fleet convention now, pre-unsealing) preserved; it edits audited bytes and would need targeted re-audit. Missing-interval convention pinned in the same entry. |
| **PIN-A21** | A3-B2 | Proposed pin: the literal frozen text and the D6 shared-convention family identify **A17's possession-weighted construction** as the preregistered reading; A21's nc rebuilt with A17's decayed-sum machinery under a remediation node with targeted re-audit. The game-weighted reading preserved as A21's implemented-but-rejected construction. |

(A3-B3 is disposed at §4, not in this table; A2-A1 at §3.)

## 7. RAISED items — proposed ratifications

1. **K0_FLAT reading — RATIFY SOUND.** `k0_flat_offset_intercept` IS "K0_FLAT" wherever frozen
   prose says K0_FLAT; the pure-intercept variant is auxiliary and never citable without its
   qualifier; diagnostic-only status confirmed in code, tests, and the cross-slice parity run
   (byte-identical across arms). No code change.
2. **P27 fold-policy — route per §5** (executor names it; coordinator ratifies the precedence
   analysis now).
3. **Bootstrap p-value — RATIFY SOUND**, condition elevated to EXEC-M3.
4. **P26 R8 call-site adjudication — RATIFY SOUND**, with R-F2 recorded: the code's
   all-tested-parameters rule is the implemented rule, strictly stronger than the P36 SPEC prose;
   nobody may later cite the SPEC wording as the implemented rule.

Severity C block: ratify the auditors' AFFIRM recommendations as compiled in `SPEC.json`
(`severity_c_disposition`); annotate the fleet record for A2-C13 (A07 test count) and CMP-1;
A3-X1 (receipt timestamp rewrites) leaves the coordinator free to restore pre-audit bytes from
the baseline commit.

## 8. Preserved disagreements (never averaged)

1. **Fold policy:** fact (i) SEASON_BLOCK-shaped S7 statement vs fact (ii) expanding operative
   masks — both on the record; (ii) proposed as governing by D006 precedence; (i) preserved as
   the S7 historical basis.
2. **A20 docstring vs n_clock_pin:** "the universe window is exactly what prior-games-only
   means" vs "the universe-row clock is barred" — both preserved; EXEC-M6 adjudicates.
3. **n_clock_pin scope:** universal text vs K6 named-arm application — document-internal
   ambiguity preserved; adjudicated once, fleet-wide.
4. **A24:** frozen "fallback: none needed" vs A14's frozen franchise-debut facts — the module is
   card-exact and the card is defective, recorded in exactly those words.
5. **A13 kill:** code's card-supported literal reading vs its own docstring's narrowing.
6. **A12 kill:** module's sign-vs-sign reading (noise edge carried) vs predicted-direction
   alternative.
7. **Sign instability / missing intervals:** two conventions each, both recorded; per-arm pins
   proposed.
8. **A21 vs A17:** one frozen phrase, two constructions, 0.27 measured divergence; A17's proposed
   as preregistered.
9. **K0_FLAT:** both readings computed and labelled forever; the offset-carrying one is the
   referent.
10. **R8 wording:** SPEC "≥ 1" vs code "all" — code governs, prose recorded.
11. **A07 test count:** 15 functions / 55 checks / fleet "54/54" — annotated, never rewritten.

## 9. Chain of custody

| audit file | sha256 |
|---|---|
| `stage2b/P37_IMPLEMENTATION_AUDIT/AUDIT_RUNNER.md` | `7EE150E028B672C3212E1CAB57560B387E33EB3BDDFC363C007EE0430645F8D0` |
| `stage2b/P37_IMPLEMENTATION_AUDIT/AUDIT_ARMS_A02_A13.md` | `5DAEEB00A959024056019DC59484C0C747C086886E24AAD3D354D88270B336EE` |
| `stage2b/P37_IMPLEMENTATION_AUDIT/AUDIT_ARMS_A14_A26.md` | `35BBFE0739ED395C9E0CA12262FBA5D15C32AC6EC93EB0DB4FBCF3527D6AF1CD` |

Cross-checked input pins (re-measured by this compiler 2026-08-06): P35 cards
`68EF22F4FCA15A2E8D91EEEB9B84B86F86E8E9E7CAAB5E23E6A9B950385B4D32`; P33
`066B2A046021DB119A75E2C847C325F6F4E40BB6E418BC7B31C8D072D347D093`. All five guard byte-pins,
`team_cities.csv`, and both frozen real input artifacts verified by all measuring auditors.
Independence attestations present in all three files; no SEALED_RESULTS read anywhere;
`P38_UNSEALED` absent throughout. Known byte side effect: auditor 3's mandated suite re-runs
rewrote seven arms' test-receipt wall-clock fields only (A3-X1); the coordinator's baseline
commit remains the canonical byte record.

## 10. Coordinator sign-off

- [ ] Ratify NO HALT / arm-level closure (§1)
- [ ] Ratify A08 remediation-in-flight scope and blocking (§3)
- [ ] Choose A24 disposition (a) or (b) and freeze the registry-appended amendment (§4)
- [ ] Ratify fold-policy precedence analysis; direct executor naming (§5, EXEC-M2)
- [ ] Ratify the EXEC-M1…M7 mandate block and the PIN-* block (§6)
- [ ] Ratify RAISED-item dispositions and the Severity C block (§7)
- [ ] Append the ratified ruling to DECISION_LEDGER.jsonl; materialize REPORT.md
