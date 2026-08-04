# P26_ARM_SPECIFIC_K0_CONTRACT — the `K0_MATCHED[arm_id]` contract and machine-readable schema

**Node:** `P26_ARM_SPECIFIC_K0_CONTRACT` · **Lane:** possession · **Type:** documentation ·
**Severity on failure:** A · **Addresses:** V2 stop-condition findings **S6** and **S9**
(with measured bearing on **S4**, **S5** and **S7**).

## Epistemic status of this output

> CONTRACT. Defines what a matched null must be for each kind of arm. It is a specification, not evidence, and it decides no arm's fate.

---

## 0. Files this node produced

| file | what it is |
|---|---|
| `REPORT.md` | this document: the contract, the measurements, the contradictions |
| `FINDINGS.json` | the machine-readable finding set |
| `K0_MATCHED_SCHEMA.json` | JSON Schema 2020-12 for one `K0_MATCHED[arm_id]` record |
| `validate_k0_matched.py` | call-site wrapper: shape check + the cross-field rules a schema cannot express + delegation to the **frozen** `comparison_gate.require_matched_k0` |
| `TESTS.py` | 41 assertions, standalone, `main()` returns 1 on failure |
| `MEASURE.py` / `MEASUREMENTS.json` | every number in section 2, re-derived from the frozen artifacts |
| `K0_MATCHED_EXAMPLES.json` | two worked records (`EXAMPLE_` prefixed — no real arm exists yet) |

Nothing frozen was edited. No git command was run.

---

## 1. The contract

### 1.1 `K0_MATCHED` is a map, not an object

`K0_MATCHED` is a **map keyed by `arm_id`**. There is no universal `K0_MATCHED`. Every arm carries
exactly one record; two records may not share an `arm_id`; an arm with no record has no
authoritative control and cannot be adjudicated.

`K0_FLAT` (intercept-only) is a **DIAGNOSTIC REFERENCE**. Beating `K0_FLAT` has **no promotion
value**. Every record must carry `k0_flat_role: "diagnostic_only"`, and the schema pins that value
with a `const` so it cannot be quietly relabelled.

### 1.2 The invariant set — what every matched null holds identical

For every arm, `K0_MATCHED[arm_id]` holds **byte-identical**: rows (as a digest, not as prose),
target, folds, weights, offset, fallback machinery, nuisance terms, and lower-order structural
terms. Operationally this is enforced as equality on **all seventeen** `comparison_gate.DIMENSIONS`
(measured: 17, listed in `MEASUREMENTS.json` `M7`) plus a redundant pin of `rows`, `target`,
`folds`, `weights` and `offset` in the record's own `invariants` block, so that a sidespec typo and
an invariant typo cannot cancel.

`target` is pinned by the schema with `const: "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"`.
A record cannot swap the primary target.

### 1.3 Exclusion minimality — the null excludes **only** the treatment mechanism

Let `T` be the arm's declared `treatment_terms`. The contract requires

```
set(arm.substantive_features) - set(k0.substantive_features) == set(T)    # exactly
set(T) INTERSECT set(k0.structural_terms) == empty                       # no re-entry
set(arm.structural_terms) == set(k0.structural_terms)                    # closure
```

Removing more than `T` is a **straw control**; retaining any of `T` is **feature absorption**.
Both block, with distinct finding kinds (`exclusion_not_minimal`,
`treatment_term_survives_in_k0`, `structural_closure_violated`).

### 1.4 Where a term is declared — the routing rule that the frozen gate forces

**Measured (`MEASUREMENTS.json` `M7`, and scenario A in section 2.8):** the frozen
`comparison_gate.k0_findings` raises the blocking kind `k0_has_substantive_features` whenever
`k0.n_substantive_features > 0`. A K0 that declares its tier main effects in `substantive_features`
is therefore **rejected by the frozen gate**, no matter how correct it is scientifically.

The contract resolves this without touching the gate:

* **structural terms** (tier main effects, fallback indicators, nuisance terms) live in
  `k0_spec.structural_terms` and are *declared* in a structural parity dimension —
  `preprocessing`, `fallback_rules` or `companion_components` — with an **identical string on both
  sides**. Layer A then enforces them: a K0 that drops the tier structure produces a
  `dimension_mismatch`, which is **not adjudicable by an ordinary reason** (scenario C, measured).
* **treatment terms** live in `arm_spec.substantive_features` and are absent from
  `k0_spec.substantive_features`, which stays empty.

Every term must appear in `declaration_routing`. A term with no route is invisible to the frozen
gate and blocks (`term_unrouted`). This is the mechanism by which the packet's phrase *"MATCHED
STRUCTURAL CONTROL — not a literally featureless model"* and the gate's *"K0 must carry ZERO
substantive features"* are made simultaneously true rather than contradictory (contradiction **X5**
below).

### 1.5 Per-arm-kind rules

`arm_kind` is declared **before results** and determines both the shape of the null and the verdict
label the arm is eligible for.

| `arm_kind` | matched null | verdict eligibility |
|---|---|---|
| `calibration_only` | the tested parameter is **fixed at its incumbent/null value** — a slope at exactly **1.0** — and the null carries the **preregistered lower-order intercept structure** | **CALIBRATION RESULT ONLY.** Never a feature-value label, however large `challenger_vs_k0` is |
| `substantive_feature` | contains **every** non-substantive structural degree of freedom granted to the candidate, and **excludes the substantive terms** | feature value, via `challenger_vs_k0` against this record |
| `structural_reparameterisation` | carries the **arm's own new parameterisation with the tested parameter at its null** — not the incumbent's old structure. An arm that dissolves the tier ladder into continuous pooling gets a control with **continuous support weighting**, not tier dummies | structural result |
| `level_transport` | the null must destroy the **claimed** signal. A permutation must act on an axis in `claimed_signal_axes` | transport result |
| `hierarchical_pooling` | pooling strength fixed at its null | pooling result |
| `observation_purification` | the purification step removed; the observation universe otherwise identical | purification result |

`calibration_only`, `structural_reparameterisation` and `hierarchical_pooling` **fix a parameter**;
the others **remove a term**. A record whose kind requires a fixed parameter and names none blocks
(`tested_parameter_missing`).

### 1.6 Marginality — lower-order closure

A treatment term of the form `FACTOR:feature` requires `FACTOR`'s **main effect** to be present in
`k0_spec.structural_terms`, unless `FACTOR` is itself substantive or itself a treatment term.
Concretely: **a candidate with tier interactions has lower-order tier main effects in its K0.**
Otherwise the interaction is credited with the main effect it never had to beat
(`lower_order_term_missing_from_k0`).

### 1.7 No credit for free flexibility

`intercept_treatment`, `calibration_freedom`, `penalty_treatment`, `link_function`,
`preprocessing`, `fallback_rules`, `companion_components` and `post_processing` must be identical
between the arm and its null. A difference on any of them is reported under its own countable code
`free_flexibility_granted`, in addition to the generic `invariant_mismatch`, so that
"no arm receives credit for free re-centring, changed fallback, or a more flexible estimator"
is a *countable* property of a report rather than a sentence in a document.

### 1.8 How S6 is resolved — per arm, by the declared mechanism

S6 states the dilemma exactly: omitting the tier partition from K0 gives a straw control; including
it kills every cold-start arm on arrival. **This contract does not answer that universally, because
S9 establishes there is no universal answer.** The rule is:

> A structural term is in `K0_MATCHED[arm_id]` **if and only if it is not part of that arm's
> declared treatment mechanism.** A term that *is* part of the treatment mechanism determines the
> `arm_kind`, and the `arm_kind` determines the verdict label.

So an arm may put the tier dummies on the treatment side — but then its mechanism is *re-centring a
partition*, its kind is `calibration_only`, and it is labelled a calibration result and is
ineligible for a feature-value claim. And an arm whose mechanism is *estimating the cold-start level
better within the ladder* faces a control that already carries tier main effects, which is the
correct, non-straw test of that claim. There is no configuration in which the same partition is both
free structure and a credited effect.

### 1.9 Fold-local estimability of the **control**

S7 lands on the control itself. **Measured:** the tier indicator is identically zero in **4 of 18**
`pace_source` x `season` cells (`league_prior_all` in 2022, 2023, 2024; `team_window_prior_season`
in 2021). Under `GATE_INVOCATION_CONTRACT` section 4 that is a blocking `zero_variance` finding *on
the authoritative control*, and the remedy must be frozen with a **numeric** trigger before any
result is visible.

Every record whose structural terms include a partition indicator must therefore carry
`fold_local_fallback` with `required`, `trigger`, a non-null `numeric_threshold` (unless the action
is `refuse_to_score_fold`), an `action` from a closed enum, and `registered_before_results: true`.
**This node declares the field and blocks on its absence; it does not set the threshold.** Setting
it is `P27_FOLD_LOCAL_ESTIMABILITY_GUARD`'s job and this node does not pre-empt it. The example
records use `1e-8`, matching `feature_gate`'s own `impossible_scaling` constant, purely so the
examples validate.

### 1.10 Call-site order

`validate_k0_matched.bind_and_require_matched_k0(record)` runs the contract checks **first** and
only then delegates to the frozen `comparison_gate.require_matched_k0`. Calling the frozen gate
alone leaves S4, S6 and S9 unenforced — **measured**, scenario E below. Nothing frozen is modified;
the enforcement is entirely at the call site, as standing rule 3 requires.

---

## 2. What I measured

Every figure below was computed by code I ran against the actual artifacts. The two artifacts and
their digests, re-derived:

```
python experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/MEASURE.py
```

* `projected_exposure_v1/team_possession_prior_v1.parquet`
  -> `c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18` — **matches**
  `EVIDENCE_PACKET_V2.sources`.
* `possessions_v2/possessions_raw_v2.parquet`
  -> `7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a` — **matches**.

The realised regulation-equivalent target is rebuilt with the same construction as
`stage2a/build_evidence_packet.py:realised_pace()`:
`n_off_poss * 40 / (40 + 5*max(0, max_period - 4))`.

### 2.1 Universe — AGREES

| quantity | measured | packet | verdict |
|---|---|---|---|
| team-game rows total | 2990 | 2990 | AGREES |
| resolved rows | 2982 | 2982 | AGREES |
| unresolved rows | 8 | 8 | AGREES |
| game clusters, resolved | 1491 | 1491 | AGREES |
| game clusters, all rows | 1495 | 1495 (as `games_with_one_shared_projection`) | AGREES |
| rows per resolved cluster | min 2, max 2 | — | NOT_IN_PACKET |

This closes the V2 packet-nit *"game_clusters 1491 and games_with_one_shared_projection 1495 sit
three lines apart over different universes"*: the two numbers are **1491 = clusters after the 8
unresolved rows are dropped** and **1495 = clusters before**. `1495 - 1491 = 4` games, each losing
both team-rows: 4 x 2 = 8. The nit is real and its cause is now measured, not inferred.

### 2.2 Pooled bias/variance — AGREES

| quantity | measured | packet | verdict |
|---|---|---|---|
| `residual_variance` (ddof=1) | 13.50014000520758 | 13.50014 | AGREES |
| `target_variance` (ddof=1) | 15.27299027376524 | 15.27299 | AGREES |
| `variance_explained_vs_target` | 0.11607748298006348 | 0.11608 | AGREES |
| `squared_bias` | 0.02533534506961617 | 0.025335 | AGREES |
| `bias_share_of_mse` | 0.0018737846493183724 | 0.001874 | AGREES |

### 2.3 S4's free-slope evidence — AGREES

| quantity | measured | S4 | verdict |
|---|---|---|---|
| `var(projected)/var(target)` | 0.15730306529044968 | 0.157 | AGREES |
| variance explained | 0.11607748298006348 | 0.116 | AGREES |

### 2.4 S6's bias share of MSE by stratum — AGREES, and the missing definition is now established

`bias_share = mean(e)^2 / mean(e^2)`, `e = projected - realised`.

| stratum | n | measured `bias_share_of_mse` | S6 | verdict |
|---|---|---|---|---|
| pooled | 2982 | 0.0018737846 | 0.00187 | AGREES |
| `team_window_same_season` | 2762 | 0.0103360412 | 0.01034 | AGREES |
| `league_prior_all` | 37 | 0.0037211069 | 0.00372 | AGREES |
| `team_window_prior_season` | 183 | 0.3709840994 | 0.37098 | AGREES |
| `season_openers` | 76 | 0.4248807466 | 0.42488 | AGREES |

**S6 does not say what "season_openers" means.** I recovered it by exhaustive match: it is
`game_no_in_season == 1`, n = 76, and only that definition reproduces 0.42488. The two neighbouring
definitions do **not**, and are recorded here because they are the ones a later reader would
naturally assume:

* `game_no_in_season <= 3` -> n = 228, bias share **0.2119262424** — NOT_IN_PACKET
* `pace_level > 1` (the tier partition itself) -> n = 220, bias share **0.2641865725** — NOT_IN_PACKET

S6's substantive claim survives re-derivation intact: the incumbent's bias is 0.19 % of MSE pooled
and 37-42 % on the cold-start strata.

### 2.5 S7's per-fold degeneracy — AGREES, all 18 cells

Counts of resolved team-game rows by `pace_source` x `season`:

| `pace_source` | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| `league_prior_all` | 28 | **0** | **0** | **0** | 3 | 6 |
| `team_window_prior_season` | **0** | 36 | 36 | 36 | 36 | 39 |
| `team_window_same_season` | 382 | 442 | 484 | 488 | 581 | 385 |

Every one of the eighteen cells matches S7 exactly. Four cells are identically zero.

### 2.6 S5's exact offset dependency — AGREES

| quantity | measured | S5 | verdict |
|---|---|---|---|
| rows with two sides | 2982 | 2982 | AGREES |
| `max abs(own + opp - 2*projected)` | 0.0 | 0.0 | AGREES |
| `corr(own_est, projected)` | 0.7738440692 | 0.7738 | AGREES |
| `corr(own_est, opp_est)` | 0.1976692869 | 0.1977 | AGREES |

Both pairwise correlations sit far below the gate's `corr_threshold = 0.999`, so the exact
three-term dependency is invisible pairwise — as S5 says. This is `P25_OFFSET_DEPENDENCY_GUARD`'s
territory; this node only requires that `invariants.offset` and
`comparison_gate_sidespec.exposure_offset` be the same declared string on both sides, and does not
implement the augmented-rank check.

### 2.7 The packet's tier justification — **CORRECTS**

`EVIDENCE_PACKET_V2.control_specification.K0_MATCHED.why_this_is_not_feature_absorption` asserts:

> "pace_level > 1 is algebraically identical to game_no_in_season <= 3 (2982/2982, zero
> off-diagonal)"

Measured, on the 2982 resolved rows:

| construction of `game_no_in_season` | agreement | off-diagonal | claim |
|---|---|---|---|
| cumcount over **all 2990** team-game rows | 2982 / 2982 | **0** | TRUE |
| cumcount over the **2982 resolved** rows only | 2974 / 2982 | **8** | FALSE |

The packet does not say which construction it means. The packet's **own producer**,
`stage2a/build_evidence_packet.py:98`, computes `game_no_in_season` on the resolved frame `res` —
the construction under which the claim is **false**. The eight discrepant rows are the 2021 fourth
games of the eight teams whose season opener is unresolved
(`pace_level == 1`, `n_history_games == 3`, `gno_full == 4`, `gno_resolved == 3`).

This matters because the claim is the **sole stated justification** for admitting the tier partition
into `K0_MATCHED`. Two things follow, and both are reasons the contract does not rest on it:

1. even under the favourable construction the equivalence is not *algebraic*, it is a consequence of
   the incumbent's own constant `MIN_HISTORY_M = 3` — change the constant and the identity
   disappears; and
2. the identity is between a tier indicator and a *schedule-position* indicator, which says nothing
   about whether the tier belongs on the control side for a *given arm*. That is S9's point, and it
   is why section 1.8 decides the question per arm rather than by this identity.

I did not edit the packet. It is frozen.

### 2.8 The frozen `comparison_gate` — what it does and does not see

Structure, measured (`MEASUREMENTS.json` `M7`):

* `len(comparison_gate.DIMENSIONS) == 17`;
* occurrences of the string `K0_MATCHED` in `comparison_gate.py`: **0**;
* occurrences of `K0_FLAT`: **0**;
* occurrences of `slope` (case-insensitive): **0**;
* `SideSpec` has **no** `arm_id`, `k0_kind` or `control_kind` field;
* `k0_has_substantive_features` fires when `k0.n_substantive_features > 0`.

So the frozen gate has **no notion of which arm a K0 belongs to**. `K0_MATCHED[arm_id]` cannot be
enforced inside it, and per standing rule 3 must not be added to it. Hence this node's wrapper.

Behaviour, measured by calling the frozen `require_matched_k0` on five constructed pairs
(reproduced as T12 in `TESTS.py`):

| scenario | frozen-gate result |
|---|---|
| A — K0's tier main effects declared in `substantive_features` | **BLOCKED** `k0_has_substantive_features` |
| B — tier main effects declared in a structural dimension, identical both sides | **PASSED** |
| C — K0 drops the tier structure (the S6 straw control) | **BLOCKED** `dimension_mismatch` |
| D — calibration arm declaring its free slope under `calibration_freedom` | **BLOCKED** `dimension_mismatch` |
| E — S4's free slope carried as a substantive column, everything else identical | **PASSED** |

Scenario E is S4, reproduced against the bytes: an arm that adds **zero information** — a pure
affine re-map of the incumbent's own output — passes strict Layer A parity untouched, and
`_headline_judgment` would print `FEATURE VALUE DEMONSTRATED`. Scenario D shows the gate *does*
catch the same flexibility when it is honestly routed. **The gate's coverage of calibration slope
therefore depends entirely on how the author routes the declaration, and nothing in the frozen gate
enforces the routing.** That is exactly what `arm_kind`, `treatment_terms` and
`verdict_label_policy` exist to force, and why the wrapper runs first.

### 2.9 Arm registry — no Stage 2B arm exists yet

`arm_registry.jsonl`: 41 records, 17 of `kind == "arm"`, and **zero** Stage 2B possession arms.
The contract is therefore written against **arm kinds**, and the two records in
`K0_MATCHED_EXAMPLES.json` are prefixed `EXAMPLE_` so they can never be mistaken for a registration.

### 2.10 Tests

```
python experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/TESTS.py
```

41 assertions, **41 pass, exit 0**. One per acceptance criterion plus a negative case for each; T12
additionally re-runs the five frozen-gate scenarios of section 2.8 inside the test so the claim
cannot rot.

---

## 3. What I could NOT establish

1. **No real arm.** Zero Stage 2B possession arms are registered (measured, 2.9). I could not
   validate a single K0 record for an arm that exists. The contract is unexercised against real
   candidates and will first be exercised at `P33`/`P35`/`P36`.
2. **The Stage 2B fold boundaries are not frozen anywhere I could find.** `EVIDENCE_PACKET_V2`
   states only *"chronological, nested by season; a game is NEVER split across folds"*. The example
   records use six season labels because that is what the data has; the actual fold set is
   `chronological_folds` and the schema requires it to be stated, but I could not verify it against
   a frozen definition because none exists yet.
3. **`pipeline_id` remains asserted, not demonstrated.** The frozen gate documents this in
   `REMAINING_GAPS` and my wrapper does **not** close it. A K0 record can declare the arm's
   `pipeline_id` while being produced by different code, and neither the gate nor this contract will
   notice.
4. **The shape checker is a stdlib subset, not a conformant JSON Schema processor.** `jsonschema` is
   not installed (measured: `import jsonschema` fails; `pandas`, `numpy`, `pyarrow` import,
   `pytest` does not). `check_schema` implements exactly the keywords the schema uses — `type`,
   `required`, `properties`, `additionalProperties`, `enum`, `const`, `minLength`, `minItems`,
   `uniqueItems`, `items`, local `$ref`. A record could exploit a keyword the schema does not use
   and the checker does not implement. The schema file itself is valid 2020-12 and can be handed to
   a real processor when one is available.
5. **The packet's intended construction of `game_no_in_season` (2.7).** The packet is frozen and
   does not say. I report both constructions rather than choosing one.
6. **Whether the tier partition *should* be in any particular arm's K0.** That is a per-arm question
   by construction (1.8) and cannot be answered before the arms exist. This node supplies the rule,
   not the answers.
7. **Nothing about performance.** No comparative historical performance of any challenger was
   inspected; `stage2b/SEALED_RESULTS` was not read and does not exist on disk.

---

## 4. Contradictions found

**X1 — frozen document vs frozen document: `K0_MATCHED` is specified as one object and as many.**
`EVIDENCE_PACKET_V2.control_specification.K0_MATCHED` is a single object with a single
`definition`, a single `excludes` list and a single `tier_partition_rule`. `V2_STOP_CONDITION.S9`,
in the same frozen directory, states that "one control construction cannot serve every arm" and
that `K0_MATCHED` "must be constructed per arm". Both are frozen; they cannot both govern. This
contract sides with S9, and that is a change to the K0 structure — see section 5.

**X2 — document vs bytes: the packet's tier justification is construction-dependent and false under
its own producer's construction.** Section 2.7. `2982/2982, zero off-diagonal` holds only when
`game_no_in_season` is counted over all 2990 team-game rows; `build_evidence_packet.py:98` counts it
over the 2982 resolved rows, where the figure is 2974/2982 with 8 off-diagonal.

**X3 — a pooled reading presented without its stratum qualification.**
`EVIDENCE_PACKET_V2.bias_variance.reading` says *"A better point estimate must reduce dispersion,
not re-centre."* I re-derive the pooled figure it rests on (0.0018738) **and** the stratum figures
that invert it (0.3709841 and 0.4248807). Both are correct; the reading carries no qualification and
is false on the strata where the wave's cold-start arms would live. S6 raised this; it reproduces
exactly.

**X4 — `comparison_gate` has no dimension for calibration *slope*, and its coverage of the one it
does have is routing-dependent.** Measured: zero occurrences of `slope` in the module; scenario D
blocks and scenario E passes, differing only in where the author wrote the same flexibility down.
`GATE_INVOCATION_CONTRACT` section 7.2 says the calibration class is `comparison_gate`'s to catch.
It catches it only when declared.

**X5 — packet label vs gate bytes on whether K0 is featureless.** The packet labels `K0_MATCHED` a
*"MATCHED STRUCTURAL CONTROL — not a literally featureless model"*; `comparison_gate` blocks any K0
with `n_substantive_features > 0` and its own docstring says K0 is "the challenger's own pipeline
with zero substantive features". Under `RESEARCH_CONTRACT_V1`'s precedence rule — *"where this
contract and a shared gate implementation appear to disagree about what a check does, the
implementation governs"* — the gate wins, and the packet's label must be read as *structural terms
exist but are not declared as substantive features*. That reading was nowhere written down before
this node; section 1.4 writes it down and `TESTS.py` T12 proves both halves against the bytes.

**X6 — a test-fixture aliasing defect worth recording.** While writing `TESTS.py`, sharing one
`dict` object between the arm sidespec and the K0 sidespec made **every** parity check pass
trivially: the two sides were the same object. Seven assertions failed only after the aliasing was
removed. This is the in-memory form of the failure that row and fold **digests** exist to prevent,
and it is recorded rather than silently fixed because an implementation node could reproduce it and
see a green gate.

---

## 5. Stop conditions

My stop condition is: *a finding would change the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set or the leakage status — HALT and
raise, do not resolve it inside the node.*

**Raised, not resolved:**

* **The K0 structure changes.** This node's own mandate — making `K0_MATCHED` per-`arm_id` — is a
  change to the K0 structure relative to the frozen `EVIDENCE_PACKET_V2.control_specification`
  (contradiction X1). I have written the specification because that is the node's brief, but I do
  **not** adopt it. The coordinator must explicitly supersede the packet's `control_specification`
  block, or explicitly reject this contract. Until then two frozen documents disagree and no arm may
  be adjudicated against either.
* **The tier-partition rule changes.** The packet's `tier_partition_rule` ("a tier or fallback
  partition may appear in K0_MATCHED ONLY when it reproduces architecture already present in the
  incumbent or challenger comparison path") is replaced in section 1.8 by a per-arm rule keyed to
  the declared treatment mechanism, with a labelling consequence. Same disposition: raised, not
  adopted.
* **The packet's justification for that rule does not hold as written** (X2). Raised. The packet is
  frozen and was not edited.

**Not tripped.** Nothing in this node changes the primary target (the schema pins it with `const`),
the inference structure (rows, clusters, weighting and resampling are consumed as given and
re-derived only to confirm them), the candidate universe (2982 / 1491 confirmed unchanged), the
cutoff-valid feature set, or the leakage status. No fit was run. No performance was inspected.

**Deferred to their owning nodes, deliberately not resolved here.**
S7's numeric fold-local trigger -> `P27_FOLD_LOCAL_ESTIMABILITY_GUARD` (this node declares the
required field and blocks on its absence).
S5's augmented-rank check over `[X | offset]` -> `P25_OFFSET_DEPENDENCY_GUARD`.
S1/S3/S8's cutoff-valid feature set -> `P22`, `P24`, `P2A`.
The primary-before-secondary ordering that S4's and E5's labelling consequences depend on ->
`P28_PRIMARY_SECONDARY_ORDERING_CONTRACT`.
