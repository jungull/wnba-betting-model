# F11 — Target contract DRAFT: player allocation / distribution architecture

**Node:** `F11_PLAYER_ALLOCATION_ARCHITECTURE` · lane `future_research` · type `documentation` ·
role: read-only research scout
**Governing contract:** `RESEARCH_CONTRACT_V1`
**Builds on:** `experiments/player_program/orchestration/reports/ROADMAP_EXTRACTION.json` (G04)

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

---

## 0. The one-line answer

**ESTIMAND: `NOT_DERIVABLE_FROM_DOCUMENTATION`.**

No document in this repository states a target statistic, a unit and a denominator for a player
allocation or distribution layer. What the documentation supplies is an *architecture* — a frozen
allocation rule, exact conservation identities, a staged causal order, and an inventory of
denominators labelled *examples* — with **nothing to grade it against**. This draft does not
supply the missing estimand and does not propose one. Inventing one here would misrepresent it as
a commitment the program has made; it has not made it.

This is the same condition G04 recorded for 13 documented tracks
(`ROADMAP_EXTRACTION.json`, `counts.needs_target_contract = 13`), and the closest of those to this
node — `M24_STAGE_CDE_TARGET_INVENTORY`, which covers "usage/possession share" — carries
`needs_target_contract: true` and `documented_target: "PARTIAL"`.

---

## 1. What the documentation actually says (verified citations)

Every quote below was read at the cited line.

| # | claim | citation |
|---|---|---|
| 1 | The origin of this node is a *ranked discovery direction*, not a target: "**Clean player-allocation proxies** — small player-level value" | `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:217` |
| 2 | That direction is explicitly non-promotable: "**Items 2–4 are discovery directions, not promotion candidates.**" | `DISCOVERY_WAVE_1_SUMMARY.md:224` |
| 3 | The allocation layer cannot move the team total: "By construction they cannot move the team total: projected exposure sums to exactly 5× projected team possessions." | `DISCOVERY_WAVE_1_SUMMARY.md:218-219` |
| 4 | The share quantity itself is recorded ABSENT: "3PA · FTA · usage/possession share · … | **ABSENT** — all seven" | `PLAYER_RESEARCH_COVERAGE_MATRIX.md:57` |
| 5 | The exposure arm affirmatively declines to define any scored quantity: `"nothing_scored": "this arm computes no accuracy, calibration, error or edge figure of any kind"` | `experiments/player_program/arm_registry.jsonl:16` (record `projected_player_possessions_v1`) |
| 6 | …and forbids looking for one in this phase: `"must_not_be_inspected_in_this_phase": ["actual-minute MAE", "possession MAE", "team-margin MAE", "calibration", "residual covariance", "betting outcomes"]` | `arm_registry.jsonl:16` |
| 7 | The frozen allocation rule: `player_off_possessions = projected_team_off_possessions * (projected_minutes / 40)` | `arm_registry.jsonl:16`, `minutes_to_possession_mapping.frozen_rule` |
| 8 | The denominator catalogue is illustrative, not frozen: the objective's `natural_opportunity_denominators` block gives a `rule`, then `"examples"`, then a `weaker_proxies` instruction to "REGISTER the weaker proxy explicitly rather than presenting it as equivalent" | `experiments/player_program/register_program_roadmap.py:59`, `:63`, `:74` |
| 9 | Possession/minute share appears in documentation only as an archetype *feature family* input — "minutes and possession share" — never as a target | `register_program_roadmap.py:181`, `:185` |
| 10 | Phase 0 requires "target and denominator **frozen**" before any fit | `RESEARCH_CONTRACT_V1.md:23` |
| 11 | The only adjacent quantity with a documented metric is **minutes**, on the team thread's incumbent, and it is gated: "The bridge to build: restrict the arm's emission to the shared key set, pin α to 0.30, and compare on the 13,450 common obligations" | `HANDOFF_PLAYER_MODEL_PROGRAM.md:185` |

### Why item 11 is not an estimand for this node

`HANDOFF_PLAYER_MODEL_PROGRAM.md` §4 does state a minutes MAE and an improvement bar for
`minutes_twostage_availability_v1`. That is a **minutes** target on the incumbent registry, blocked
behind `M10_SCORING_AUTHORISATION_GATE` and `M12_MINUTES_BRIDGE_SPECIFICATION` in G04's catalogue.
It is not an allocation estimand: it grades a per-player-game level, not a within-team distribution,
and it says nothing about a denominator, a share, or a conservation constraint. Borrowing it and
calling it this node's estimand would be exactly the invention this node is forbidden to make.

### Proving the negative

The searches that returned nothing were confirmed to work. Grep for `possession share|usage
rate|usage_rate|minutes share|minute_share` across `PLAYER_RESEARCH_COVERAGE_MATRIX.md`,
`ROADMAP.md`, `HANDOFF_PLAYER_MODEL_PROGRAM.md` and all of `experiments/player_program/` returned
**positive** hits at `PLAYER_RESEARCH_COVERAGE_MATRIX.md:57`, `register_program_roadmap.py:181`,
`build_projected_exposure.py:409`, `HYPOTHESIS_LEDGER.json:21` and elsewhere. The machinery hits
these strings; every hit is a *feature*, a *diagnostic label*, or an *ABSENT* entry. None is a
target definition. The absence of an estimand is a measured absence, not a failed search.

---

## 2. Measured architecture — what an estimand would have to attach to

Produced by `MEASURE.py`; raw values in `MEASUREMENTS.json`.

**The conservation identity holds exactly, within each evidence regime.**
Max absolute deviation of the per-team-game player-possession sum from 5× the projected team
offensive possessions is **8.88e-16** in all three regimes; team minutes sum to 200 in every
team-game (`min 199.99999999999997`, `max 200.00000000000003`).

**The allocation layer has ONE free quantity, and it is minutes.** In the primary regime the
identity `projected_off_possessions == projected_minutes/40 × projected_team_off_possessions`
holds with max absolute difference **0.0** (defensive side likewise 0.0), and projected minute
share equals projected possession share to **5.55e-17**. A "possession allocation" arm and a
"minutes allocation" arm are therefore, under the frozen mapping, the *same arm*. Any future
allocation estimand must say which of the two it is grading, or it is grading neither.

**Caution for anyone repeating this measurement:** the artifact stacks three evidence regimes in
one file (120,262 rows over 2,988 team-games). Pooled across regimes the player-possession sum is
10–15× the team total, not 5×. The 5× identity is per regime. Read `regime` first.

---

## 3. Matched-K0 requirement for this target

`K0_MATCHED` is **per arm_id, never one universal object**, and `K0_FLAT` is diagnostic only.
The binding shape is `experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/
K0_MATCHED_SCHEMA.json` (`$id: player_program/stage2b/k0_matched/1`), with the cross-field rules
implemented in the sibling `validate_k0_matched.py` — a record that satisfies the schema and fails
the validator is not a valid specification.

**The requirement, stated for this target:**

1. **There is no K0 to state yet, because there is no arm and no estimand.** `K0_MATCHED` is a map
   keyed by `arm_id`; with no registered allocation arm the map has no key. A K0 cannot be written
   before the estimand, because the schema requires `invariants.target` to be held *identical*
   between arm and null, and `target` is precisely what this draft cannot supply.
2. When an estimand does exist, the matched null must hold **identical rows, target, folds,
   weights, offset, fallback machinery, nuisance terms and lower-order structural terms**, and must
   exclude **only** the treatment mechanism under test.
3. **The allocation-specific hazard, from measurement, is the renormalisation.** Because the layer
   is team-total-pinned by construction (§2), any allocation candidate necessarily reallocates mass
   under a fixed total. The matched null must therefore perform the *identical* renormalisation with
   the mechanism removed — the no-proxy control shape used in discovery wave 1: "Wfree/WKfree
   renormalise the NO-PROXY arm the same way, controlling for 'is the reallocation gain the
   proxy's, or just a relaxed Arm-D coefficient?'" (`HYPOTHESIS_LEDGER.json:702`) — so that a gain
   is attributable to the
   mechanism and not to the re-centring. A null that does not renormalise identically grants the
   candidate free flexibility of exactly the kind `comparison_gate.py` exists to catch.
4. The arm must declare its `arm_kind` **before results**; the enum in the schema is
   `calibration_only | substantive_feature | structural_reparameterisation | level_transport |
   hierarchical_pooling | observation_purification`. There is no `allocation` kind. Whichever is
   chosen constrains the verdict label the arm is eligible for, and an arm may not be scored under
   a kind it did not declare.
5. The **exposure offset is not a free parameter**. Projected minute share is a deterministic
   transform of the exposure offset (`HYPOTHESIS_LEDGER.json:26`); an allocation arm and its K0
   must carry the same offset or the comparison is unmatched.
6. `K0_FLAT` may be reported as a diagnostic and may never carry the decision.

---

## 4. Cutoff-valid evidence — inventoried, not assumed

All counts measured from the bytes by `MEASURE.py`. **Availability is not eligibility; eligibility
is not admission.**

### 4.1 Projection side

`experiments/player_program/projected_exposure_v1/projected_player_possessions_v1.parquet`
— 120,262 rows, 1,495 games, 2,988 team-games, 386 players, all `player_game_contract/5`.

| regime | evidence_class | rows | team-games | games | `information_available_at_cutoff` | `historically_captured_asof` | `operationally_plausible` | `production_eligible` |
|---|---|---|---|---|---|---|---|---|
| `tier_a_only` (**PRIMARY**) | `primary` | 35,629 | 2,914 | 1,458 | true | true | true | **false** |
| `tier_a_plus_tx_b` | `sensitivity_transaction` | 39,790 | 2,988 | 1,495 | **false** | false | false | **false** |
| `tier_a_plus_tx_b_plus_s2` | `weak_diagnostic_s2` | 44,843 | 2,988 | 1,495 | true | false | false | **false** |

Regime flag values reproduce `PROJECTED_EXPOSURE_RECEIPT.json` `config.REGIME_EVIDENCE` exactly.

**Consequences that must not be softened:**

* **`production_eligible` is `false` on all 120,262 rows.** No regime is production evidence.
* Only the **primary** regime is cutoff-valid *and* as-of-captured. It covers **2,914** of 2,988
  team-games; **74** team-games exist in the widest regime and not in the primary one, and **76**
  primary-regime team-games are `unresolved_insufficient_candidates` (fewer than 5 viable
  candidates; nothing emitted, no player invented).
* The second regime is **not** cutoff-valid (`information_available_at_cutoff: false`); it uses
  retrospective effective dates. It is a sensitivity arm and can never be pooled with the primary.
* The third regime is cutoff-valid but not as-of-captured — weak prior-season affiliation. Labelled,
  never pooled.

### 4.2 Cutoff policy is not uniform across seasons (primary regime)

| season | `exact_tip_T-90m` rows | `date_only_prior_day_cutoff` rows | team-games |
|---|---|---|---|
| 2021 | 0 | 4,850 | 406 |
| 2022 | 0 | 5,563 | 466 |
| 2023 | 0 | 6,150 | 508 |
| 2024 | 0 | 6,096 | 512 |
| 2025 | 4,866 | 2,573 | 607 |
| 2026 | 5,395 | 136 | 415 |

An exact-tip cutoff exists only from 2025. Any allocation evaluation with a chronological fold
structure crosses a **cutoff-policy change inside the evaluation window**, and the earlier folds
are held to a weaker information standard than the later ones. This must be disclosed, not
averaged away.

### 4.3 Fallback structure (primary regime)

`pred_is_fallback` is **true for 4,850 of 4,850 rows in 2021** — every 2021 primary row rests on a
fallback prediction. 2022–2026 fallback rows: 643, 679, 600, 737, 1,075. Cold-start rows in the
primary regime: 1,280 of 35,629.

### 4.4 Rotation plausibility (primary regime, per team-game)

`plausible` 1,916 · `degraded_roster_cardinality` 989 · `degraded_both` 5 ·
`degraded_extreme_scaling` 4 · `unresolved` 76. **998 of the 2,914 allocated primary team-games
(34.2%) carry a degraded plausibility label** — most often more than 12 players receiving minutes.
These labels are declared to be pure labels: none feeds back into the allocation
(`build_projected_exposure.py:387`).

### 4.5 Realised (outcome-side) evidence that a future estimand would be graded against

* `possessions_v2/possessions_raw_v2.parquet` — 238,563 possessions, 1,495 games, 2,990 offensive
  team-games, with a valid ten-player on-court lineup on **238,060** and invalid on **503**. Every
  one of the 2,914 primary team-games has realised offensive-possession rows, and all of them have
  valid-ten rows: **0** primary team-games lack either. A realised player-possession denominator is
  therefore *constructible*.
* `turnover_targets_v1/player_turnover_targets_v1.parquet` — 28,328 rows, 2,990 team-games, 384
  players, all `scoreable`, `rate_defined` on 28,271 (57 not), carrying both `minutes` and
  `realised_off_possessions`.

**Constructible is not admissible.** The registry declares `player_possessions/2` a "REALISED
historical reconstruction" that "cannot be used as forecast exposure" (`arm_registry.jsonl:16`,
`why_a_new_arm`), and the exposure arm's stop boundary forbids inspecting possession or minute
error in this phase (§1 item 6). Nothing in this inventory authorises touching it.

### 4.6 The cutoff-validity flags are themselves asserted

`PROGRAM_STATE.json` open gap `cutoff_validity_asserted`, Severity **B**, `implemented: false`:
"cutoff_valid is asserted per source and bound into the receipt forever, but it is a property of
upstream construction and cannot be verified from bytes." What is inventoried above is the *flag
values as they exist in the artifact*, measured; the flags' truth is a provenance assertion, not a
byte-level proof.

---

## 5. Known data blockers

1. **No estimand** (§0). Everything else is downstream of this.
2. **The ideal denominators do not exist in the data.** The objective's preferred denominators —
   "per touch, possession used, pass or drive", "per potential assist, touch or teammate conversion
   opportunity" (`register_program_roadmap.py:63-73`) — require tracking data the repository does
   not have. Discovery wave 1 carried this as a mandatory disclosure: none of its six proxies
   "observes touches, passes, drives, time of possession or potential assists"
   (`HYPOTHESIS_LEDGER.json:630`). Any allocation denominator here is a **weaker proxy** and must be
   registered as one, never presented as equivalent (`register_program_roadmap.py:74`).
3. **`production_eligible` is false everywhere** (§4.1). There is no production-eligible exposure
   evidence at all.
4. **Primary-regime coverage is 2,914 team-games over 1,458 games**, not the possession target's
   2,982 over 1,491. An allocation universe is **not** the primary possession universe; the two
   must not be conflated in any fold or cluster-bootstrap design.
5. **34.2% of primary team-games carry a degraded rotation-plausibility label** (§4.4).
6. **Cutoff policy changes mid-window** (§4.2) and 2021 is entirely fallback (§4.3).
7. **Severity A, carried from G04, unresolved:** `general_feature_producer_provenance`,
   `implemented: false`, "blocks any fitted arm whose feature producer emits no construction
   receipt" (`PROGRAM_STATE.json`, `open_methodological_gaps`). Only `possession_features.py` emits
   a producer construction receipt. An allocation feature producer would need one before any fit.
   G04 raised this as Q10; this node does not resolve it.
8. **Scoring is unauthorised.** `M10_SCORING_AUTHORISATION_GATE` is a human gate and the escalation
   is still open (`ROADMAP_EXTRACTION.json`, item `M10`). No outcome-comparing metric on any player
   target may be computed until it closes.
9. **The 51 played player-games that are not obligations** (`HANDOFF_PLAYER_MODEL_PROGRAM.md`
   §P-D2) are a shared-contract universe question, not a modelling question. An allocation universe
   inherits it.
10. **Dual-frame binding** is recorded closed for `dual_frame_audit` in `PROGRAM_STATE.json`
    (`implemented: true`, `closed_by: PLAYER_DUAL_FRAME_AUDIT_v2`) while `RESEARCH_CONTRACT_V1.md:36`
    still reads "contractually required but not yet fully implemented". Recorded as a documentation
    lag, not adjudicated here (§7).

---

## 6. What a future estimand would have to state (form only — deliberately unfilled)

Listed so that the gap is legible, **not** as a menu to be selected from. Filling any of these is a
registration act reserved to a preregistration and an independent gate review.

* the **statistic**: a within-team share, a per-player count, a distribution, or a calibration
  quantity — the program has not chosen;
* the **unit of observation**: player-game, player-game-regime, team-game composition vector;
* the **denominator**: which of the ABSENT Stage-C opportunity denominators, and registered
  explicitly as a weaker proxy where the ideal one is unavailable;
* the **row universe** and its exclusions, in the shape `turnover_target_contract_v1` uses
  (`arm_registry.jsonl:29`): grain, included, excluded-and-counted, players changing teams;
* the **conservation requirement** the target inherits (team minutes to 200; player possessions to
  5× team possessions);
* the **evidence regime** it is defined on, and the statement that regimes are never pooled;
* the **metric and sign convention**, frozen before results.

---

## 7. Contradictions and tensions found

1. **Coverage matrix vs. artifact (apparent, resolved).** `PLAYER_RESEARCH_COVERAGE_MATRIX.md:57`
   records "usage/possession share" as **ABSENT**, while
   `projected_player_possessions_v1.parquet` emits a projected possession share for 120,262 rows.
   These are consistent: the matrix is inventorying Stage-C *opportunity targets*, and the artifact
   is a forecast-exposure bridge that explicitly scores nothing. Recorded so nobody later reads the
   artifact as closing the matrix row. It does not.
2. **`RESEARCH_CONTRACT_V1.md:36` vs. `PROGRAM_STATE.json`.** The contract says dual-frame auditing
   is "contractually required but not yet fully implemented"; the state file records
   `dual_frame_audit` as `implemented: true`, `closed_by: PLAYER_DUAL_FRAME_AUDIT_v2`. The state
   file is authoritative for scientific state and is derived, so the contract prose is most likely a
   documentation lag — but this node does not have the authority to reconcile them and does not.
   Reported.
3. **No contradiction between any document and the bytes was found for the 5× identity or the
   200-minute constraint.** Both hold to floating-point tolerance (§2).

---

## 8. Stop conditions

The node's stop condition — *a finding would change the primary target, the K0 structure, the
inference structure, the candidate universe, the cutoff-valid feature set or the leakage status* —
**was not tripped.** This draft changes none of them: it defines no target, registers no arm,
proposes no feature, and alters no universe. The Severity A gap in §5 item 7 is carried forward
from G04 (Q10), not newly raised here.

---

## 9. This draft does not authorise fitting

**Plainly: this document does NOT authorise fitting.** It is not a target contract; it is a record
that the target contract does not exist and cannot be written from what is documented. It confers
no authorisation to fit a model, register an arm, construct a feature, compute an outcome-comparing
metric, or open `experiments/player_program/stage2b/SEALED_RESULTS/`.

Fitting requires **all** of: a target contract, a matched K0, cutoff-valid evidence, a
preregistration, and an independent gate review. This node supplies none of the five. It supplies
an inventory of what the fourth would have to survive.

A registered layer with a stability report and no estimand is not closer to fittable than an
unregistered one. It is a well-specified procedure with nothing to grade it against — which is
exactly what the player allocation architecture is today.

---

## 10. Files

| file | role |
|---|---|
| `TARGET_CONTRACT_DRAFT.md` | this document |
| `REPORT.md` | auditable prose report: what was measured, what could not be established |
| `MEASUREMENTS.json` | machine-readable measurements |
| `MEASURE.py` | the script that produced every number above |
