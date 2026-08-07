# S32_CANDIDATE_SYNTHESIS — REPORT BODY

SYNTHESIS. Reduces the frozen ideation wave plus the D047 directed set to mechanistically
distinct score-family arms. Every rejection below is a design decision, not an empirical
result: nothing has been fitted, no sealed result was read, and no performance number
appears anywhere in this node's outputs.

**Node:** `S32_CANDIDATE_SYNTHESIS` · **Lane:** score, cycle 2.
**Deliverables:** `CANDIDATES.json` and this file, both in this directory. Nothing else was
written anywhere. The coordinator materializes the official REPORT.md from this body per the
harness rule; this node writes no file named REPORT.md.

---

## 1. What was verified, and with what

**Input hash verification (all five MATCH).** Rederived in this session with
`Get-FileHash -Algorithm SHA256` over raw file bytes and compared to the frozen values in
`S31_SCORE_IDEATION/RAW_SOURCES_MANIFEST.json`:

| file | frozen sha256 (prefix) | result |
|---|---|---|
| raw_sources/SOURCE_1_state_space.md | 7a91f278... | MATCH |
| raw_sources/SOURCE_2_domain.md | 7cf0612d... | MATCH |
| raw_sources/SOURCE_3_forecasting.md | 8a039ce7... | MATCH |
| raw_sources/SOURCE_4_falsificationist.md | e3eb064a... | MATCH |
| raw_sources/SOURCE_5_information.md | a756fad2... | MATCH |

**Candidate census, counted from the documents themselves** (headings, not memory):
SOURCE_1 proposes 8 (SS1–SS8), SOURCE_2 proposes 7 (C2-1–C2-7), SOURCE_3 proposes 8
(F3-1–F3-8), SOURCE_4 proposes 4 (its section 0 states the shortness is deliberate),
SOURCE_5 proposes 8 (M1–M8). **Union = 35.**

**Output validation.** `python -c "import json; json.load(open(...CANDIDATES.json))"` passes.
Reconciliation arithmetic, computed over the written file (not asserted): 12 retained arms,
28 dropped-log entries (19 MERGED + 9 DROPPED), 7 ideation candidates retained as canonical
forms; 7 + 19 + 9 = 35 = the union. 9 mechanism families; 18 (arm, estimand) elements.

**Ledger quotations.** D047's directive text as quoted on the directed arms was copied
byte-for-byte from `orchestration/DECISION_LEDGER.jsonl` entry `D047_CYCLE2_SCOPE_CONFIRMATION`
in this session; D042/D043 carriage terms likewise from `D042_P40_CLOSE` and
`D043_CYCLE2_SCORE_AND_EFFICIENCY`.

**Binding law.** The FROZEN FULL `CYCLE2_TARGET_CONTRACT.md` was read in full. Sections
leaned on hardest: §1 (closed schedule-identity column set, as-of-cutoff valuation, OT
discipline), §2 (coverage floors ≥90% pooled / ≥80% per fold; selection made visible),
§4 (element = (arm, estimand); families frozen by mechanism; disputed assignments dual-run
with the stricter result governing; kills uncorrected; K0 null-strength floor pinned to
bytes; containment reading), §5 (covariance obligation for side-splitting arms), §7
(directed candidates enter at S32 with provenance labels; directed candidates never count
toward independent-source tallies; identification constraint mandatory for every directed
candidate, F12 §4.4 carry-forward; cycle-1 nulls bind — rest/schedule/home forms act on
scoring, not pace), §8 (market fields barred outright; injury/availability barred for
2021–2026; F13 cutoff-valid inventory governs UNPROVEN fields via S37 promotion).

**Format precedent.** Cycle-1 `P32_CANDIDATE_SYNTHESIS` was read and its discipline
adopted: merge only when mechanism AND design column coincide up to affine recoding or a
preserved choice set; never average conflicting frozen conventions (its D6/D7 lesson);
log every non-retained candidate with one named reason; preserve rather than silently
resolve source disagreements; an audit idea can survive the death of its arm (its R5
pattern, used twice below).

---

## 2. The synthesis logic

Three principles, applied in order:

1. **The null already knows the composite.** Contract §4's null-strength floor grants every
   K0 the frozen public composite's ingredient columns by byte-pinned identity. Any
   candidate whose signal is a re-expression of pace × lagged-efficiency team strength has
   expected Δ ≈ 0 by construction. This principle killed C2-1 outright (§5, R-01) and
   shaped every retention toward information or geometry the linear byte-pinned floor
   structurally cannot carry.
2. **Survival economics govern df and estimand registration.** Cycle 1 fitted 29 elements
   and passed 0. SOURCE_4's discipline — minimum estimand set, pinned constructions, one or
   two fitted coefficients, pre-pinned signs, subset-located kills with magnitude arithmetic —
   was adopted as the house style. Where a state-space source and SOURCE_4 proposed the same
   mechanism, the low-df form is canonical and the richer form is a recorded escalation
   variant (SS6→SC11 is the explicit case; SS1's dynamics→SC10 implicitly). Weak estimand
   registrations were declined even when a source offered them (E3 declined on SC03, SC05,
   SC12; E1 declined on SC06; E2/E3 declined on SC07).
3. **Convergence is evidence of naturalness, never a count.** Where several isolated sources
   proposed one mechanism independently, that fact is recorded once per mechanism in the
   `convergences` block, the formulations are merged into one canonical arm with dual
   provenance, and the merged candidates appear in the dropped log as MERGED. Directed
   candidates never enter any tally (contract §7, restated on every directed arm).

The slate that results: **12 arms, 18 elements, 9 mechanism families** — roughly 60% of
cycle 1's element count, concentrated on the five directed areas plus the four strongest
independent convergences.

---

## 3. The directed candidates (D047, quoted exactly)

Each directed arm's JSON entry carries the D047 verbatim text it implements and its
mandatory identification constraint (F12 §4.4 carry-forward). Summary of the judgment calls:

* **SC01_OPP_ADJ_INTERACTING** implements D047 p1: "per-side offensive/defensive strength
  components where each game's realized efficiency is read relative to the opponent's
  concurrent strength (joint/iterative adjustment permitted), combined across the two teams
  (off_A x def_B and off_B x def_A) rather than single-team averages." Three sources
  converged on this structure independently (SS1's observation equation, C2-2, M1) — the
  directive's flagship family is also the wave's third-strongest convergence. The additive
  bilinear ridge form (off_i − def_j per side, sum-to-zero identified) is canonical; it reads
  each realized efficiency against the opponent's concurrent strength exactly as directed,
  with "joint/iterative adjustment permitted" honored by the joint ridge fit. Registered on
  all three estimands — the only arm in the slate given three elements — because the
  directive targets the score family broadly; the E1 element is named as the weakest and the
  family pays for it knowingly. As a side-splitting arm it carries the §5 covariance receipts
  in full. D047 p4's honesty clause is carried onto the arm: A26 was null for SOS-adjustment
  ON PACE; efficiency is the untested question.
* **SC04/SC05 (home court)** implement the contract §7 rendering "home-court structure from
  a single constant upward" as a two-rung ladder: league-drift first (SOURCE_4's 1-df form,
  4-source convergence), team offsets second (3-source convergence — and 3-source convergent
  *skepticism*: all three predicted shrinkage collapse, recorded on the arm rather than
  suppressed).
* **SC06 (rest/travel)** merges all five sources' fatigue candidates — the wave's strongest
  full convergence — onto SOURCE_4's pinned-index 1-df chassis, with the D047-mandated 2024
  charter break as an explicit era-interaction coefficient (SOURCE_2's contribution) and an
  era-split receipt that doubles as the §7 explicit-modeling obligation. Acts on scoring
  only; the cycle-1 pace retry bound is respected by construction.
* **SC07 (referee crews)** had zero ideation convergence — recorded honestly, with the
  mitigating note that the isolated sources had no referee fields in their ingredient
  inventory, so absence of convergence is weak evidence here. The arm is registered with two
  blocking preconditions rather than on faith: historical crew columns must exist in owned
  data, and the *upcoming* game's crew assignment is outside the contract's closed
  schedule-identity set — consuming it needs S34 set-extension plus a receipted pregame
  cutoff-validity showing that does not rest on vendor-asserted retrospective timestamps
  (the P2B standard). If either fails, the arm lapses without penalty to the slate. This is
  the honest reading of a directive naming a mechanism whose data admissibility nobody has
  yet established.
* **SC02 (A07)** is re-registered fresh per D042/D043: the cycle-1 near-miss may never be
  cited toward promotion; the form moves from pace to scoring (retry bound); τ = 5 stays
  pinned; and the concentration-kill diagnostic (Δ by n≤5 vs n>5 stratum) is a **mandatory
  receipted output of the sealed run** — its absence is a card defect. The cycle-1
  collinearity pattern (A07 vs depth) is anticipated: condition-number failure in ≥2 folds
  retires the arm unevaluated, carried verbatim from the cycle-1 registration.

## 4. The convergences (every one)

| mechanism | independent sources | n | disposition |
|---|---|---|---|
| early-season initialization / carryover | SS4, C2-6, F3-2, S4-carryover, M6 | **5/5** | canonical SC03; F3-2 and M6 dropped with reasons (§5); A07 shares the habitat, not the column |
| schedule fatigue on scoring | SS7, C2-4, F3-6, S4-fatigue, M3 | **5/5** | canonical SC06 |
| home advantage beyond a constant | SS8, C2-5, S4-HCA, M2 | 4/5 | SC04 + SC05; includes convergent skepticism on the team component |
| modeled margin dispersion for E3 | SS2/SS3, C2-7, F3-4, M7 | 4/5 | canonical SC08 |
| opponent-adjusted interacting strength | SS1, C2-2, M1 (+F3-3 partial) | 3/5 | canonical SC01 (directed overlap dual-labeled) |
| recent-form/trend beyond level | SS1-dynamics, F3-1, M8 | 3/5 | canonical SC10 |
| explicit OT bridge | SS3, C2-1, F3-7 | 3/5 | **no arm** — elevated to card-level ingredient hygiene (see R-06) |
| robustified prior-game inputs | C2-3, F3-8 (+SS5 partial) | 2/5 | canonical SC12 |
| referee crews | — | 0/5 | USER_DIRECTED only (SC07) |

The OT-bridge row is the one convergence deliberately not given an arm: three sources
agreed the regulation-equivalent pace ingredient needs a lagged-OT-rate treatment inside a
full-game estimand, and F3-7's own median-vs-MAE arithmetic shows the *fitted* version is
expected null under the declared metric. The convergence therefore survives as a mandatory
card declaration for any arm consuming the pace ingredient, not as a gate-taxing element.

## 5. Every dropped candidate, with its reason

Merged candidates (19) are listed in `CANDIDATES.json.dropped` with their canonical homes;
the mechanism-level reasoning is in §2–§4 above. The nine outright drops, each a named
design decision:

* **R-01 · C2-1 (pace×efficiency recombination):** duplicate-of-null-floor. D043 p1
  describes the immediate composite baseline as "verified-pace-ingredient ... times
  strictly-lagged efficiency (points-per-possession EWMAs, offense and defense)" — the very
  ingredients §4 grants the K0 by byte identity. The candidate re-estimates its own null;
  the source itself flagged the risk. Its OT bridge survives via CONV_OT_BRIDGE.
* **R-02 · SS5 (Student-t tails):** below-resolution df spend — its E3 value lives in the
  two extreme calibration bins where clustered CIs are widest (its own statement) and its
  fitted ν is expected effectively Gaussian; the robust-filtering half is partially
  expressed by SC12.
* **R-03 · F3-2 (James–Stein shrinkage-to-field):** family-crowding judgment call, and the
  synthesis's most contestable drop, flagged as such for S33 review. Its habitat and its
  games are SC03's; retaining both would put six elements in the early-season family and
  tax the slate's largest-magnitude candidate. The genuinely distinct increment
  (shrink-to-field vs import-prior-season) is preserved as a variant note on SC03's card.
* **R-04 · F3-3 (diverse combination):** the diversity premise fails against a shared
  information basis — every component is a recombination of the same lagged score history
  the null-granted ingredients span; the source's own K1 names the exact failure and its
  cross-candidate note 3 generalizes it. The component-error-correlation receipt is
  preserved as an adjudication-lane recommendation (P32 R5 pattern).
* **R-05 · F3-5 (Platt recalibration):** below-resolution insurance layer by its own
  account, independently corroborated by SOURCE_4's rejection of E3-only recalibration
  arms. Preserved as an explicit `calibration_freedom` card dimension option — which the
  contract requires declared anyway — not an arm.
* **R-06 · F3-7 (OT expected-value correction):** its own arithmetic predicts the fitted
  θ ≈ 0 under MAE (median target); a candidate whose design predicts its own null
  coefficient is not survival-grade. Convergence preserved as card hygiene (§4).
* **R-07 · M4 (composition channels):** S37-conditional on CUTOFF_UNPROVEN channel columns
  with a declared no-fallback ("the mechanism is not registrable"), plus the full §5
  covariance obligation and a floor-reproduction failure mode. Future-cycle material.
* **R-08 · M5 (style matchup interaction):** same S37 conditionality, plus second-order-
  statistic instability and declared variance-sharing with M1/SC01. Dropping both M4 and M5
  leaves the composition/style channel **deliberately unexplored this cycle** — the slate's
  one known coverage gap, stated here so it is a choice on the record, not an oversight.
* **R-09 · M6 (continuity-weighted carryover):** conditional on owned lagged
  player-identity box rows whose existence is an unverified inventory question (the
  source's own registration condition); its unconditional degradation duplicates SC03's
  span by the source's own admission. The continuity increment is preserved as a labeled
  optional upgrade note on SC03's card, contingent on the S37 inventory answer.

## 6. Family partition recommendation and disputes

Nine mechanism families (member lists in `CANDIDATES.json.families`). Three assignments are
disputable and are flagged for the §4 dual-partition rule (stricter result governs):

1. **FAM_S2_EARLY_SEASON:** {SC02, SC03} together (shared habitat) vs split (transient
   level-deviation vs initialization-information are different claims).
2. **FAM_S2_BLOWOUT_DISCOUNT:** {SC09, SC12} together (one epistemic claim: blowout
   observations overstate their information) vs split (output-geometry vs input-hygiene;
   the proposing sources treated them as unrelated).
3. **Lagged-league-drift merge:** SC04 and SC11 are the same pinned construction on
   different channels (home-margin vs total). Merge reading {SC04, SC11} vs the split
   reading (different estimands, different mechanisms).

The partition freezes at S33/S35, not here. Per the contract there is no program-wide FWER
claim; the additive bound is stated at S35 with the frozen family count.

## 7. Judgment calls a reviewer should probe

Beyond R-03 (named above as the most contestable drop):

* **SC01 registered on three estimands.** The directive's breadth was read as licensing
  three elements for the flagship family; a stricter survival reading would register E2/E3
  only. The E1 element is the one to cut if S33 disagrees.
* **1-df re-forms of state-space candidates** (SS6→SC11 explicitly; the pattern generally).
  This synthesis judged that fitted innovation variances on a 1,491-cluster panel repeat
  SOURCE_1's own predicted degeneracies, and that the pinned-EWMA + single-β form tests the
  same mechanism at maximal power. The richer forms are recorded as escalation variants,
  not silently discarded.
* **SC07's preconditions** could have justified dropping the referee arm entirely; it is
  retained because D047 directs it, with the preconditions made blocking instead. If S33/S34
  cannot discharge them, the lapse is already priced in.
* **Pinned constants inherited from sources** (λ=0.5, K=10 on SC03; index weights on SC06;
  knee=8 on SC09; halflife 60 on SC04/SC11; τ=5 on SC02): these are a-priori pins from the
  frozen sources or the cycle-1 registration, adopted unchanged precisely so that no
  tuning surface opens at synthesis. S33 may re-pin with justification but every grid point
  it opens charges the family budget.

## 8. What could NOT be established, and why

1. **Whether the frozen composite's ingredient columns carry cross-season initialization.**
   SC03's premise (and part of SC02's) is a falsifiable claim about a specific deficiency of
   the public floor. This is checkable at S33 from the frozen builder source/parameters —
   legitimate non-performance information — but was not checkable here without reading
   artifacts outside this node's inputs. If the ingredients do carry carryover, SC03 dies
   cleanly at the gate, which is its designed outcome.
2. **Whether referee-crew columns exist in owned committed data, and whether pregame crew
   assignment is witnessable for 2021–2026.** Outside this node's read scope; SC07 is
   conditional on both.
3. **The exact CUTOFF_VALID/UNPROVEN status of the channel columns** (3PA rate etc.) named
   by M4/M5/C2-7. The F13 inventory itself was not among this node's binding inputs; the
   drops rest on the sources' own conditionality statements plus the contract's §8 rule that
   UNPROVEN fields need receipted S37 promotion.
4. **Whether exp(-n/5) is near-collinear with the null-granted ingredient columns on the
   score design.** The cycle-1 A07-vs-depth pattern may recur against the composite's
   ingredients; the condition-number receipt and the ≥2-fold retirement rule are carried so
   the question resolves mechanically at audit, not rhetorically here.
5. **Universe counts** (1,491 clusters / 2,982 rows) are quoted from the frozen contract §2,
   not re-derived — the data artifacts are outside this node's read scope.
6. **The S32B K0 schema's canonical nesting declaration** (contract §4: whether null-granted
   terms must appear in the arm's own design). Every retained arm declares containment
   compatibility, so the slate is safe under either reading; but final comparison
   declarations wait on the frozen schema.

## 9. Prohibitions honoured

No fit was performed and no performance number appears in this node's outputs. Nothing
under `stage2b/SEALED_RESULTS` or `stage3_score/SEALED_RESULTS` was read, listed, or
globbed. No frozen artifact was modified. Git was not run. All writes are inside
`experiments/player_program/stage3_score/S32_CANDIDATE_SYNTHESIS/`, and no file named
REPORT.md was written by this node. This node does not mark its own work accepted;
downstream review (S33 onward) governs.
