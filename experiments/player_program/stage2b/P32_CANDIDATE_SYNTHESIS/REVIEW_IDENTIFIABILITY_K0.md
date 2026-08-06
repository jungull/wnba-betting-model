# P32_CANDIDATE_SYNTHESIS — ADVERSARIAL REVIEW: IDENTIFIABILITY AND K0-PARITY

Reviewer lens: identifiability and K0-parity (one of two independent reviewers).
Epistemic status of the object under review, carried verbatim: SYNTHESIS. Reduces sources to
families. Rejection here is a design decision, not an empirical result: nothing has been fitted.

## STOP-CONDITION STATEMENT (up front, as required)

**No stop condition tripped in my judgment.** The closest calls, examined explicitly:

- **D1 (opposite carryover nulls, A11 vs A12):** this determines what one arm's K0 *contains*,
  not the K0 *structure* (the per-arm K0_MATCHED map of D007 stands unchanged). I probed the
  synthesis's argument on this and it holds: resolution is a receipts question assigned to
  P33–P37, and both candidate nulls are nested, matched constructions. Not a structure change.
- **Finding F3 below (A04's null is incoherent under one of its two basis options):** this is a
  defect in one arm's declared null, fixable by making the null's lower-order main effect track
  the basis choice. It does not alter the K0 structure, the inference structure, or leakage status.
- Nothing in the union or the synthesis touches the primary target, the candidate universe
  (2,982/1,491), the cutoff-valid feature set as adjudicated by the packet, or leakage status.

## HASH VERIFICATION — ALL_MATCH

All ten pinned files were re-hashed over raw bytes (`Get-FileHash -Algorithm SHA256`) in this
session before anything was relied on. Every one MATCHES its frozen value:

| file | result |
|---|---|
| P32_CANDIDATE_SYNTHESIS/SPEC.json (f71fc445…) | MATCH |
| P32_CANDIDATE_SYNTHESIS/REPORT.md (175a17f1…) | MATCH |
| P31 GENERATION_ORDER_V3.json (898f4b80…) | MATCH |
| HYPOTHESES_adversarial_identifiability.md (bf589616…) | MATCH |
| HYPOTHESES_calibration_control.md (1085da13…) | MATCH |
| HYPOTHESES_coldstart_fallback.md (8d145ce1…) | MATCH |
| HYPOTHESES_cutoff_leakage.md (3d8c096b…) | MATCH |
| HYPOTHESES_opponent_mechanism.md (88cda948…) | MATCH |
| HYPOTHESES_timeseries_shrinkage.md (ea2cbd42…) | MATCH |
| P30 EVIDENCE_PACKET_V3.json (95d2412c…) | MATCH |

Also re-measured, not trusted: SPEC arithmetic (20 families, 26 arms, 5 rejections, 26+5=31;
30 provenance citations covering all 31 source sections with AI-H4 only in the rejection ledger —
all reconcile, verified by a python pass over the SPEC in this session). The two embedded tool
hashes I could check against the packet both match (postgame_surrogate_guard 951e8513…,
ACTIVE_SET_RULE_PREREGISTRATION 327fa8ec… — both present verbatim in the frozen packet bytes).

## BLINDNESS ATTESTATION

I did not read, list, or glob the other reviewer's output (any other REVIEW_* file in this
directory), and I did not read, list, or glob anything under
`experiments/player_program/stage2b/SEALED_RESULTS`. Files read: the ten pinned inputs above,
the P32 prompt, V2_STOP_CONDITION.json, RESEARCH_CONTRACT_V1.md (precedence lines),
GATE_INVOCATION_CONTRACT.md (§4), and packet subsections. No git commands were run. No fit was
performed; no performance number appears here. This is the only file I wrote.

---

## FINDINGS (severity A = would invalidate/admit leakage; B = must fix before preregistration; C = record)

### F1 — SEVERITY B — A04's cross-family collapse rule names the WRONG ARM (A08 for A09), three times

`SPEC.json` F04/A04 `notes`: "Overlap with F08 (A08) flagged: both test evidence-depth-dependent
gain … one on a rebuilt lagged deviation (A08, new construction). If P25 finds A08's rebuilt
deviation near-affine to the offset's deviation, A08 collapses into this family and must be
withdrawn…"

F08's arm is **A09_evidence_depth_adaptive_shrinkage** (TS1, w(n)=n/(n+kappa) on the rebuilt
deviation — the depth-dependent-gain twin). **A08_league_lag_level is F07** (TS4, league level
transport) and tests a different mechanism entirely. A09's own notes carry the rule correctly
("this arm collapses into F04 and is withdrawn"), so the SPEC contradicts itself. This is
load-bearing: the note defines a withdrawal-on-audit-failure rule, and an implementer or the P33–P37
node following A04's text would attach the collapse rule to the wrong arm — potentially withdrawing
the league-level-transport arm on a depth-gain redundancy finding, or failing to withdraw A09.
Fix: A08 → A09 in A04.notes (three occurrences).

### F2 — SEVERITY C — A02's distinctness note names the wrong arm (A14 for A16)

F02/A02 `notes`: "Mechanistically distinct from A14 (residual momentum)…". A14 is the expansion
intercept decay (F11); the residual-momentum arm is **A16_lag_residual_own_minus_opp** (F13). No
operational rule attaches to this note, so C rather than B, but it is an error in a frozen
definition document and the distinctness rationale for A02 is anchored to the wrong object.
Together with F1 this is a pattern: arm-id cross-references in `notes` were not validated the way
the counts were.

### F3 — SEVERITY B — K0-PARITY: A04's declared null is incoherent under its kernel basis option (fake-positive channel)

A04's hyperparameters offer two depth-response bases: binary `1[SHALLOW]` or the CF-H2 kernel
`1/(1+depth/5)`. The declared null is fixed as `[off | 1[SHALLOW] | (off − m_bar)]` — tier main +
global slope — and the formula hardcodes `alpha_S*1[SHALLOW]` regardless of basis. If the kernel
basis is selected, the treatment is `delta_S * B(depth) * (off − m_bar)` with `B` continuous, but
the null carries no `B(depth)` main effect and no kernel-shaped lower-order structure. Per
`k0_matched.core_rules` ("tier interactions require lower-order tier main effects in K0") and per
the S4 lesson the synthesis itself cites ("a free slope the control lacks is the confound"), the
interaction under the kernel basis owes a lower-order main the null lacks. Under that combination
the treatment can reject by capturing a smooth depth-indexed gain/level profile that the binary
tier main cannot represent — an information advantage over the declared K0 that would fake a
positive, exactly the failure class this arm was constructed to avoid. Note the irony: A04 adopted
the "stricter null" from CC-H4, but that null is only strict FOR THE BINARY BASIS; grafting CF-H2's
kernel into the choice set without basis-matching the null quietly re-imports part of the weaker
CF-H2 null structure that R3/D1a claims to have superseded.
Fix (either): (a) require the null's lower-order mains to be basis-matched — when the kernel basis
is selected, K0 carries the kernel main `B(depth)` (and the global slope) in place of `1[SHALLOW]`;
or (b) drop the kernel basis from A04's choice set and leave it recorded only in R3/D1a.

### F4 — SEVERITY B — MECHANISTIC DISTINCTNESS: F03 (A03) vs F06's A07 — no established separation; the dedup standard was applied inconsistently

A03 tests `alpha_S * 1[pace_evidence_depth ≤ threshold]` (shallow-evidence level error, story:
fallback pulled toward a drifted league prior). A07 tests `delta * exp(−n_i/5)` (story:
league-common early-season tempo transient). Both are level corrections beside the offset indexed
by a monotone decreasing function of accumulated evidence, and both predict the same observable
pattern: early/shallow rows share a common signed deviation from the offset. The claimed separation
rests entirely on `pace_evidence_depth` diverging materially from the within-season completed-game
count `n_i` — a relationship nothing in the packet or the SPEC establishes, and which CF-H3 itself
concedes is near-monotone in at least train_lt_2022 ("depth ≈ monotone in n"). Where the synthesis
found the analogous overlap between F04 and F08 (depth-indexed gain on two substrates), it flagged
it in BOTH arm definitions and declared an explicit P25-adjudicated collapse/withdrawal rule. For
A03/A07 it declared nothing: the two live in different mechanistic families AND different declared
multiplicity families (CALIBRATION_CONTROL_FAMILY vs COLDSTART_FALLBACK, itself D2-conflicted), so
one underlying mechanism could be tested twice under two alpha budgets and "discovered" twice.
The within-fold S7 collinearity checks A07 declares run against *depth in its own null*, not against
A03's tier column in a different family — they do not close this channel.
Fix: add a declared cross-family near-affinity rule for A03/A07 mirroring the A04/A09 rule (if the
S7/P25 audit finds `exp(−n/5)` near-affine to the A03 tier design in the training folds, one of the
two is withdrawn as a design duplicate, named in advance which), or justify the separation at
P33–P37 from the receipted construction of `pace_evidence_depth` (no performance peeking needed).

### F5 — SEVERITY B — ARM COMPLETENESS: seven arms are not buildable from their definitions without a judgment call (unenumerated grids/choice sets)

The acceptance criterion is "complete arm definitions… not counts". The following arms name a
tunable but do not bound or enumerate it, so a competent implementer (or the preregistration node)
must invent multiplicity-relevant content:

- **A03**: `shallow_threshold` — "preregistered single value or small grid"; no value, no bound.
- **A06**: drift basis option 2 — "preregistered monotone transform g"; the transform CLASS is
  unbounded (AI-H5 gave only "e.g. index/season_length").
- **A08**: `K_trailing_window_games` — "small preregistered value or grid"; unbounded.
- **A09**: `kappa` — "preregistered grid"; no elements.
- **A10**: `lambda` — "preregistered grid"; no elements.
- **A11**: `rho` — "preregistered grid"; no elements.
- **A16**: `k_window_games` — "ONE preregistered value"; the value is named nowhere in any source
  or in the SPEC.

The incompleteness originates in the sources (TS1–TS3 said "preregistered grid" without values;
AI-H1 said "single value" without one), and the synthesis correctly charges every grid point to the
family budget. But the SPEC's claim of complete arm definitions overstates: these seven are complete
as falsifiable hypotheses, not as build specifications. Contrast the CL/OM arms (A17–A24, A18/A20/
A26), where every constant is a number. Per my mandate, an arm needing a judgment call is B minimum.
Fix: the SPEC (or a P33–P37 binding note attached to it) must convert each open grid to a finite
enumerated set before any fit, and replace "small" with the enumeration obligation stated per arm.

### F6 — SEVERITY B — ARM COMPLETENESS: the "frozen inference specification" that fixes the link is never identified, and three incompatible notations coexist

`shared_estimator_convention` places every arm "under the link fixed by the frozen inference
specification" — but the SPEC gives no path and no hash for that specification. Meanwhile the arm
formulas are written in three notations inherited from the sources: `linear predictor = off + …`
(A01–A06), `eta_i = offset_i + …` (A07, A12–A15), and `log E[y] = log(offset) + …` (A08–A11), plus
`y ~ offset(log mu_incumbent)` (A16, A23, A25). If the link is log, then "off" entering the
predictor additively and `log(offset)` entering as offset are different objects, and treatments like
`(off − m_bar)` need a declared scale (raw-scale projection centered, entering as a column on the
link scale — presumably, but the SPEC does not say). Nested-null recovery at zero treatment holds
under any consistent reading, so this is not a K0-parity break — arm and null share whatever the
resolution is — but it is a genuine implementation judgment call touching 15+ arms, and the
"complete arm definitions" criterion fails on it.
Fix: name the frozen inference specification by path+sha256 in SPEC.json, and add one sentence
fixing the scale convention for centered-offset treatments (A01, A02, A04).

### F7 — SEVERITY C — A23's independent choice sets manufacture two variants no source proposed

R2 merged OM-H4 into A23 and turned the disagreements into choice sets: `cap_days ∈ {4, 7}` and
`season_opener_rule ∈ {AI-S7-fallback, OM-cap-assign}` — selected INDEPENDENTLY. The sources
proposed two bundles: (cap 7, S7 fallback) and (cap 4, cap-assign). The cross-product admits
(cap 4, S7 fallback) and (cap 7, cap-assign), which nobody proposed. Preservation of disagreement
would carry the two source-consistent bundles; the cross-product is synthesis-time candidate
manufacture, mild because the mechanism is unchanged and the multiplicity budget is charged either
way. Recommend pairing the options into the two source bundles at P33–P37.

### F8 — SEVERITY C — an unrecorded fifth convention divergence: raw vs regulation-equivalent trailing pace (A26 vs A08/A09/A10/A11/A16)

D6 preserves four incompatible trailing-WINDOW conventions. There is a fifth divergence the ledger
does not record: A26's `raw_t` is the raw per-team-game possession row count ("OT games enter raw
on BOTH sides of every mean, preregistered as-is"), while the TS arms and A16 define trailing pace
as REGULATION-EQUIVALENT (A12 even rescales prior-game OT possessions explicitly). A26's ground for
this — "the correction contrast differences OT noise symmetrically" — is a source assertion, not a
measurement (own and opponent face different OT histories, so the cancellation is approximate), and
the synthesis carried it without flagging it in the disagreement ledger. No leakage channel (all
strictly lagged) and no downstream-mismatch value channel is engaged, so C: record it beside D6 so
the preregistration node cannot silently harmonize the units either.

### F9 — SEVERITY C — R5's named reason slightly mislabels an audit arm; outcome correct

AI-H4's source proposed it as a normalization-leak DETECTOR that preregisters non-promotion; its
declared value is the audit, not exploitation. The rejection category
"downstream-mismatch-exploitation-only" imports the V2 E5 finding (trailing OT rate arbitrages the
OT bias downstream) onto an arm whose own source had already removed it from the promotion
universe. The rejection outcome is right and consistent with the source's intent, and the audit
content is preserved as a recommendation — but strictly, the candidate's "only value" was never
exploitation, it was diagnosis. Record-level nit; no change required beyond noting it.

### F10 — SEVERITY C — D8 phrasing subtly misstates GENERATION_ORDER

SPEC D8 says GENERATION_ORDER "records isolation-directory copies existed for four sources".
GENERATION_ORDER's deviation text says four sources RECOVERED their isolation directory, and the
byte-identical/hash-verified parenthetical attaches to the two thin sources' committed-location
copy versus "the isolation copy" — implying isolation copies existed for those two as well. The
substance of D8 (the timeseries source's "only copy in existence" is an overstatement) stands
either way. Immaterial; recorded for exactness.

---

## SWEEPS BEHIND THE FINDINGS

### Mechanistic distinctness (criterion 1)

I attempted a data-generating story separating every questionable family pair among the 20:

- **F03 vs F06(A07)**: FAILED to separate without an unestablished premise — Finding F4.
- **F04 vs F08**: separable only if the incumbent projection contains structure beyond the flat
  lagged deviation (EWMA discounting, K=200 shrinkage, opponent blend — it does, per its frozen
  description), and the synthesis carries the correct collapse rule for the case it does not.
  Adequate — but the rule's arm-id is wrong (Finding F1).
- **F06(A06) vs F07(A08)**: separable — a mid-season league-wide tempo shift (e.g. officiating
  emphasis) moves the trailing realized league mean but not the schedule-position pattern; a pure
  calendar transient does the reverse under a stationary league level. Genuine.
- **F06 internal (A06 vs A07)**: calendar clock (cluster-constant) vs team game-count clock
  (within-cluster variation under staggered schedules) — different predictions on clusters where
  the two teams' n differ. Keeping both as arms of ONE family is the right call.
- **F09 vs F13**: EWMA-vs-flat contrast of league-mean-relative deviations (own only) vs
  own-minus-opp momentum of projection-relative residuals. Separable: a DGP where the incumbent's
  projection errors persist but the team's league-relative deviation is stationary fires A16 and
  not A10.
- **F13 vs F20**: projection residual momentum vs opponent-mix correction built WITHOUT the
  incumbent's projections. Separable (schedule-luck DGP fires A26 only if the incumbent fails to
  schedule-adjust; A16 keys on the projection itself).
- **F14 vs F15**: duration composition vs terminal-event creation channel. Partially entangled
  (forced live-ball turnovers ARE short possessions, so A17's short_def component partially encodes
  A19's mechanism), but the columns differ (duration_sec vs end_reason), both sources declared the
  CL pair one multiplicity family, and the synthesis preserved that. Acceptable.
- **F10(A13) vs F17(A22)**: both lagged-lineup constructions; cross-season Jaccard as carryover
  MODERATOR (interaction) vs within-season churn main effect. Different predictions; distinct.
- **F18 internal (A23/A24)**: antisymmetric vs symmetric components of (rest_own, rest_opp) —
  orthogonal projections, correctly one family, two arms.
- **Rejected duplicates R1–R4 re-derived independently**: R1 (±1 home coding is affinely identical
  to 0/1 beside offset+intercept — exact, correct rejection); R2 (same functional class, constants
  preserved as choice sets — correct, with the F7 caveat); R3 (same mechanism/feature, kernel is a
  basis — correct as dedup, with the F3 caveat on how the kernel was grafted); R4 (same mechanism,
  same feature material, monotone basis preserved — correct). **No rejected duplicate is actually a
  distinct mechanism wrongly collapsed.**

### K0-parity (criterion 3)

Every one of the 26 arms declares a per-arm matched null; I checked each against
`k0_matched.core_rules` and the S4/S5/S6/S9 dispositions:

- Nested-null recovery at zero treatment: holds for all 26 as declared.
- Lower-order rule: satisfied everywhere EXCEPT the A04 kernel-basis combination (Finding F3).
- S6 trap both directions: A07/A12/A13/A14/A15 all correctly grant depth-level/re-centring freedom
  to the null while withholding the substantive term — verified against the coldstart source text.
- S9/level-transport: A06 and A08 both explicitly ban the team-identity-permutation null and bind
  to the nested null. Correct, and correctly carried from AI-H5/TS4.
- No arm gains machinery its null lacks: imputation rules (E=3, |P|=1 churn:=0, n=0 fallbacks) are
  declared identical in arm and null everywhere they exist; A05's fold-2026 §4 fallback is declared
  in advance with the four-fold effective evidence base stated; A13's ordered nesting on A12 is
  declared. The offset-affine treatments live only inside the declared calibration family (F01–F05),
  which is precisely the P25/R11 carve-out.
- Nuisance sets differ across arms (CL arms carry is_playoff_game as nuisance; OM arms carry none)
  — permitted under the per-arm contract, symmetric within each arm/null pair, so no parity break;
  noted so nobody later compares raw "improvement over K0" magnitudes across families as if the
  nulls were common.

### Hyperparameter separation and D6 (criterion 4)

- The four D6 window conventions were each re-checked against source text: CL froze h=10/λ=0.5
  "not tunable" explicitly; OM froze same-season-flat/E=3 explicitly; TS declared grids inside the
  family budget; AI declared one preregistered k (unnamed — Finding F5). None of the frozen
  constants is an evasion of the grid: freezing before any fit spends no alpha and is the sources'
  right; the synthesis neither averaged them nor pooled them, and it binds P33–P37 not to harmonize
  without charging the budget. Faithful.
- No scientific claim found smuggled into a grid, with one borderline case: A04's basis choice set
  is arguably two functional hypotheses (threshold vs smooth saturation) dressed as a
  hyperparameter — tolerable as nuisance shape, but it is what produces Finding F3.
- One tunable frozen as if hypothesis-adjacent: A17's 8-second transition threshold — declared
  fixed by its source pre-fit, correctly placed under `hyperparameters.fixed`. Acceptable.

### Preserved disagreements D1–D8 (criterion 5)

Each was re-read against both source texts. D1, D1a, D2, D3, D4, D5, D6, D7 are preserved
faithfully — both readings present, neither averaged, each stamped on the affected arms; D1a's
stricter-null adoption is correctly grounded in RESEARCH_CONTRACT_V1's precedence line ("the
stricter governs", verified in the contract) and S4. D3's retention of A05 follows the packet's own
S7 known-degeneracies clause verbatim (verified in the packet). D8 is substantively right with the
F10 phrasing nit. None trips a stop condition on inspection: D1 is arm-level null content; D2/D5
are alpha-budget partition questions, not one of the six frozen dimensions.

---

## VERDICT

**ACCEPT_WITH_REQUIRED_CHANGES.** The synthesis is strong: the dedup standard is real (mechanism +
design column, not prose), the rejection ledger is honest and complete, the per-arm K0 discipline
is applied with more care than any prior wave, and every disagreement I could find in the sources
is in the ledger except the raw/regulation-equivalent units divergence (F8). But it does not yet
meet two of its own acceptance criteria without changes: arm completeness (F5, F6) and internally
consistent mechanistic-distinctness bookkeeping (F1, F3, F4).

Required changes, in order:

1. **(F1)** Correct A04.notes: A08 → A09 (three occurrences); the collapse rule must target
   F08/A09. Also correct A02.notes: A14 → A16 (F2).
2. **(F3)** Make A04's null basis-matched (kernel main effect in K0 when the kernel basis is
   selected), or strike the kernel basis from A04's choice set and leave it in the R3/D1a record.
3. **(F4)** Declare a cross-family near-affinity/collapse rule for A03 vs A07 (named in advance,
   P25/S7-adjudicated, mirroring the A04/A09 rule), or record a receipts-based justification of
   their separation as a P33–P37 obligation.
4. **(F5)** Attach the enumeration obligation per arm for every open grid/choice set (A03, A06,
   A08, A09, A10, A11, A16): finite elements fixed at preregistration before any fit, each element
   charged to the declared family budget; delete "small" as a specification.
5. **(F6)** Identify the frozen inference specification (path + sha256) in SPEC.json and fix the
   scale convention for centered-offset treatment columns.

C findings (F2 folded into change 1, F7, F8, F9, F10) are for the record and the preregistration
node's awareness; none blocks acceptance once the required changes land.

Disagreement with the other reviewer, if any, should be preserved by the coordinator; I have not
seen their file and nothing here is coordinated with it.
