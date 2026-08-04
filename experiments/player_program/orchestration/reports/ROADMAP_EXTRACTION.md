# ROADMAP_EXTRACTION — the documented remaining program, converted to proposed graph nodes

**Node:** `G04_PROGRAM_ROADMAP_EXTRACTION` · lane governance · type documentation · severity C

## Epistemic status

> VERIFIED_READ_ONLY_DERIVATION of what the documents already commit to. Where documentation is absent the node must record NEEDS_TARGET_CONTRACT and must NOT invent a scientific target.

That line bounds what this report may be cited for. It is a reading of documents, not a finding
about basketball, about any arm, or about any model's quality. No metric was computed. No sealed
directory was opened. No comparative historical performance was read.

---

## 1. What this node did

It read the program's own planning documents, converted what they **commit to** into proposed graph
nodes, and refused to propose anything the documents do not authorise. The output pair is:

* `experiments/player_program/orchestration/reports/ROADMAP_EXTRACTION.json` — machine-readable, with an `items` array
* `experiments/player_program/orchestration/reports/ROADMAP_EXTRACTION.md` — this file

**Every citation in both files was mechanically verified.** The generator takes each citation as a
triple `(path, line, substring)` and aborts the whole build if the substring is not present at that
exact line of that file. Six citations failed on the first three runs and were corrected against the
files rather than the other way round. No citation in either output is asserted; each one was
matched.

Generator: `build_roadmap_extraction.py` (scratchpad; not part of the repository). The check that
enforces the rule is:

```python
def cite(path, n, sub):
    actual = line_of(path, n)
    if sub not in actual:
        raise AssertionError(f"CITATION FAILED {path}:{n} ...")
    return {"path": path, "line": n, "quote": sub}
```

Three further invariants are enforced before the file is written, and each aborts the build:

1. no proposed id collides with an existing `PROGRAM_GRAPH.json` node id;
2. every proposed dependency resolves to an existing node id or another proposed id;
3. `authorises_fitting` is `False` on every item, and the mandate text is scanned for
   fitting-authorisation phrasing.

## 2. What was measured

| quantity | value | how |
|---|---|---|
| existing nodes in `PROGRAM_GRAPH.json` | 64 | `json.load(...)['nodes']`, length |
| proposed items emitted | 42 | `len(ITEMS)` after all assertions passed |
| items marked `NEEDS_TARGET_CONTRACT` | 13 | count of `needs_target_contract=True` |
| items carrying authorisation to fit | 0 | asserted, not counted: the build refuses otherwise |
| id collisions with existing nodes | 0 | set intersection, asserted |
| records in `experiments/player_program/arm_registry.jsonl` | 41 | parsed line by line |
| of those, roadmap registrations with `authorises_execution: false` | 3 | `player_program_objective_v2`, `player_archetype_discovery_layer`, `player_program_capability_matrix_and_lanes` |
| files under `experiments/cbs_v14_player_oof/attempt_001` | 81 | directory listing |
| files under `experiments/cbs_v15_player_oof_v5/attempt_001` | 75 | directory listing |

The declared validation command was run and exits 0:

```
python -c "import json,sys; d=json.load(open('experiments/player_program/orchestration/reports/ROADMAP_EXTRACTION.json')); sys.exit(0 if d.get('items') else 1)"
```

## 3. Proving the negatives

This program has already produced one manufactured negative from a silently-failing string match, so
every "not modelled" claim below rests on a search that was first shown to return hits.

The coverage probe counted case-insensitive occurrences of 60+ terms in the raw
`PROGRAM_GRAPH.json` bytes. It returned **non-zero** counts for `multiplicity` (4), `denominator`
(7), `props` (5), `market` (7), `injury` (13), `block` (75), `P3` (68), `aging` (6), `zone` (2),
`news` (1), `construction receipt` (1), `Stage 2` (1) — and each of those hits was then located to a
specific node and read in context, which is how `denominator` was found to belong to the six
future-research target-contract templates rather than to any event channel, and `aging` to a
substring of "packaging" (5 of its 6 hits).

Against that working search, the following returned **zero** occurrences in the entire graph:

`possession_prior` · `team_possession` · `rebound` · `assist` · `foul` · `free throw` · `steal` ·
`substitution` · `archetype` · `RAPM` · `garbage` · `shotchart` · `prediction_contract_v5` ·
`bakeoff` · `hierarchical` · `distributional` · `simulation` · `CRPS` · `validator_lineage` ·
`fresh_execution` · `nonlinear` · `pipeline_id` · `forgery` · `cutoff_validity` ·
`producer provenance` · `WS2` · `WS5` · `WS7` · `feasibility` · `player-grain` · `Hansen` ·
`Model Confidence` · `effective-trial` · `execution-side` · `sportsbook` · `closing line` ·
`Kelly` · `bankroll` · `referee` · `cbs_` · `v14` · `v15` · `Tier A` · `Tier B` · `candidacy` ·
`obligation completeness`.

## 4. The single largest structural finding

**The graph does not model the player-target program at all.**

`PROGRAM_GRAPH.json` carries 64 nodes across six lanes. Twenty-seven of them are the `possession` lane (`P20`-`P2A`, `P30`-`P43`, `R11`, `R12`); the rest are governance, data, operations, product and
future-research scouting. Not one node names the four player targets the program is chartered to
build — `p_active`, `e_minutes_given_active`, `attempts_usage`, `player_scoring_distribution` —
their contract, their evaluation grid, their modelling hierarchy, or their aggregation gate. The
strings `cbs_`, `v14`, `v15`, `Tier A`, `candidacy` and `obligation completeness` do not occur in
the file.

Twenty-two of the 42 proposed items are in that gap. This is not a criticism of the graph, which was
seeded from the V2 halt packet and says so; it is the largest documented commitment that the graph
does not yet represent.

## 5. What is documented, and what is only wished for

Thirteen items carry `NEEDS_TARGET_CONTRACT`. In every one of them the documents supply a *direction*
and, often, a great deal of design detail — clustering methods, leakage rules, shrinkage
requirements, denominators, stability-reporting lists — while never stating **the estimand, its
unit, and the metric it is graded on**. Design detail is not a target. Where the estimand is missing
the item says so and stops; it does not fill the hole.

The clearest case is the archetype layer. `register_program_roadmap.py` gives it a bounded challenger
set, a k-selection rule, soft-membership handling, six leakage-and-chronology constraints, an
eight-item stability report and an explicit bar — and describes the thing it must improve only as
"player-event forecasts". That is a fully specified *method* attached to an unnamed *target*, and a
node that invented one would be manufacturing a commitment.

The five event channels are the same shape with one difference: the registered objective does supply
a candidate denominator for each (rebound opportunities, defensive possessions, blockable attempts,
potential assists, fouls per defensive possession), but labels the whole block `examples` and
attaches a rule that a weaker proxy must be **registered explicitly, never presented as equivalent**.
So the denominators are candidates, not contracts, and the items are marked PARTIAL and
`NEEDS_TARGET_CONTRACT` rather than DOCUMENTED.

## 6. Nothing here authorises fitting

Every item carries `authorises_fitting: false`. Where a document names a genuine research direction —
team-possession-total projection, the gated role-expansion challenger, the hierarchical arm, the
location-and-context expected-points components — the proposed node is a **target-contract draft**,
because fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
and an independent gate review, and none of those are in this node's gift.

Two documents make that reading mandatory rather than cautious. `PROGRAM_STATE.json` records
`experiment_currently_authorized: false` and a stop boundary of eight prohibitions, among them
*"begin another event channel (rebounds, assists, blocks, fouls, shots)"* — which is precisely the
class five of the proposed items describe. And the wave summary's own phrasing for its ranked-first
item is *"the most defensible next substantive step, **if authorised**"*.

Thirty-three of the 42 items record at least one documented blocker. Nothing in this file lifts one.

---

## 7. Proposed nodes — the player-target lane (absent from the graph)

The four contract targets, their universe, their evaluation grid, the modelling hierarchy and the aggregation gate. Nothing in this group may compute a metric before `M10` is answered.

| id | title | target | NTC | fit? | gate |
|---|---|---|---|---|---|
| `M10_SCORING_AUTHORISATION_GATE` | User authorisation for the first outcome-comparing step on the player targets | DOCUMENTED | no | no | human |
| `M11_CONTRACT_V5_STAGE2_READINESS` | Adjudicate contract-v5 Stage 2 readiness against artifacts that already exist on disk | DOCUMENTED | no | no | - |
| `M12_MINUTES_BRIDGE_SPECIFICATION` | Specify the minutes bridge between the registered incumbent and the contract path | DOCUMENTED | no | no | - |
| `M13_STAGE_AB_EVALUATION_GRID` | Freeze the Stage A/B evaluation reporting grid before any of it is computed | DOCUMENTED | no | no | - |
| `M14_HIERARCHICAL_ARM_TARGET_CONTRACT` | Target-contract draft for the preregistered hierarchical player arm (rung 3) | DOCUMENTED | no | no | - |
| `M15_DOWNSTREAM_AGGREGATION_GATE_CONTRACT` | Target contract for the player-to-team aggregation gate, with the covariance requirement | DOCUMENTED | no | no | - |
| `M16_PROJECTED_SUBSTITUTION_TIMING` | Projected substitution-timing model — named as a missing dependency, no target stated | ABSENT | **yes** | no | - |
| `M17_GENERATIVE_SIMULATION_LAYER` | Generative simulation layer — accounting constraints documented, estimand not | PARTIAL | **yes** | no | - |
| `M18_ARCHETYPE_LAYER_TARGET_CONTRACT` | Archetype layer — registered design, unnamed target statistic | PARTIAL | **yes** | no | - |
| `M19_LINEUP_CHEMISTRY` | Lineup chemistry and pairings — future track, no target | ABSENT | **yes** | no | - |

### `M10_SCORING_AUTHORISATION_GATE`

*User authorisation for the first outcome-comparing step on the player targets* — lane `player_targets`, type `decision`, documented target **DOCUMENTED**.

Obtain, or record the continued absence of, the user authorisation to compute outcome-comparing metrics on the player targets. Nothing downstream of it may run without it. This node decides nothing scientific; it records a standing escalation.

**Blocked by (documented):** standing escalation to the user, still open.

**Authorising citations** (each verified against the exact line):

* `HANDOFF_PLAYER_MODEL_PROGRAM.md:250` — "escalation is still open"
* `HANDOFF_PLAYER_MODEL_PROGRAM.md:263` — "authorisation to compute outcome-comparing"
* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:25` — "**SCORING** unauthorised; escalated to the user and still open"
* `MISSION_LEDGER.md:1704` — "profitability remain **unauthorised**, and are now escalated to the user"

### `M11_CONTRACT_V5_STAGE2_READINESS`

*Adjudicate contract-v5 Stage 2 readiness against artifacts that already exist on disk* — lane `player_targets`, type `audit`, documented target **DOCUMENTED**.

The v5 spec declares Stage 2 'not yet authorised'. The worktree nevertheless already carries experiments/cbs_v14_player_oof/attempt_001 (81 files) and experiments/cbs_v15_player_oof_v5/attempt_001 (75 files). Establish which of these were produced under which contract version and authorisation, and reconcile the documents to the bytes. Do NOT fit, refit or score anything.

**Blocked by (documented):** Stage 2 not authorised (V5 spec); M10_SCORING_AUTHORISATION_GATE for any metric.

**Proposed dependencies:** `G02_DOCUMENT_INDEX`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md:288` — "Stage 1"
* `experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md:292` — "Stage 2"
* `HANDOFF_PLAYER_MODEL_PROGRAM.md:198` — "Generate `cbs_v14_player_oof`"
* `PLAYER_RESEARCH_LEDGER.md:56` — "**None.**"

### `M12_MINUTES_BRIDGE_SPECIFICATION`

*Specify the minutes bridge between the registered incumbent and the contract path* — lane `player_targets`, type `documentation`, documented target **DOCUMENTED**.

Write the bridge specification the handoff names: restrict the arm's emission to the shared key set, pin alpha to 0.30, and define the comparison over the 13,450 common obligations with the 51 reported rather than dropped. Specification only — executing the comparison is scoring and is gated on M10.

**Blocked by (documented):** M10_SCORING_AUTHORISATION_GATE.

**Proposed dependencies:** `M10_SCORING_AUTHORISATION_GATE`.

**Authorising citations** (each verified against the exact line):

* `HANDOFF_PLAYER_MODEL_PROGRAM.md:185` — "The bridge to build: restrict the arm"
* `HANDOFF_PLAYER_MODEL_PROGRAM.md:200` — "Build the minutes bridge"

### `M13_STAGE_AB_EVALUATION_GRID`

*Freeze the Stage A/B evaluation reporting grid before any of it is computed* — lane `player_targets`, type `documentation`, documented target **DOCUMENTED**.

Freeze the full reporting grid the program owes for the availability and conditional-minutes targets — pooled micro, macro-by-player, minutes-weighted, by role, by history bucket, by team, by season, calibration, interval coverage, obligation completeness, cost — as a preregistered specification. Computing any cell is scoring.

**Blocked by (documented):** M10_SCORING_AUTHORISATION_GATE.

**Proposed dependencies:** `M10_SCORING_AUTHORISATION_GATE`.

**Authorising citations** (each verified against the exact line):

* `HANDOFF_PLAYER_MODEL_PROGRAM.md:204` — "Stage A/B evaluation on the full reporting grid"
* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:129` — "## 4 · Evaluation surface"
* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:131` — "All of it is BLOCKED on SCORING"

### `M14_HIERARCHICAL_ARM_TARGET_CONTRACT`

*Target-contract draft for the preregistered hierarchical player arm (rung 3)* — lane `player_targets`, type `documentation`, documented target **DOCUMENTED**.

Draft the target contract for player_model_bakeoff_v1's dynamic-hierarchical arm: estimand, unit, denominator, matched-K0 requirement, cutoff-valid evidence inventory. State explicitly that the draft does not authorise fitting. The v5 spec bars any hierarchical challenger until the unchanged v14 baseline is established.

**Blocked by (documented):** v5 spec: no hierarchical challenger before the unchanged v14 baseline; M11_CONTRACT_V5_STAGE2_READINESS.

**Proposed dependencies:** `M11_CONTRACT_V5_STAGE2_READINESS`.

**Authorising citations** (each verified against the exact line):

* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:87` — "3 · hierarchical with player effects"
* `HANDOFF_PLAYER_MODEL_PROGRAM.md:207` — "Hierarchical arm (`player_model_bakeoff_v1`), then Stage C/D/E"
* `experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md:295` — "No hierarchical challenger"
* `PLAYER_RESEARCH_LEDGER.md:344` — "3 · hierarchical with player effects"

### `M15_DOWNSTREAM_AGGREGATION_GATE_CONTRACT`

*Target contract for the player-to-team aggregation gate, with the covariance requirement* — lane `player_targets`, type `documentation`, documented target **DOCUMENTED**.

Draft the aggregation gate contract. It must require, for every aggregation candidate, home/away residual variance, covariance, corr(e_home, e_away), and the resulting margin variance and MAE — the binding precedent from bottomup_3pt_channel_v1. Drafting only.

**Blocked by (documented):** M10_SCORING_AUTHORISATION_GATE for any measured comparison.

**Proposed dependencies:** `M13_STAGE_AB_EVALUATION_GRID`.

**Authorising citations** (each verified against the exact line):

* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:160` — "Downstream gate"
* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:215` — "corr(e_home, e_away) is a first-class reported quantity"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:282` — "any aggregation experiment must report home/away residual variance"

### `M16_PROJECTED_SUBSTITUTION_TIMING`

*Projected substitution-timing model — named as a missing dependency, no target stated* — lane `player_targets`, type `documentation`, documented target **ABSENT**, **NEEDS_TARGET_CONTRACT**.

The capability matrix names a projected substitution-timing model as the dependency that would separate offensive from defensive exposure, and records that it does not exist. No estimand, unit, denominator or metric is stated for it anywhere in the documents read. Mark NEEDS_TARGET_CONTRACT; do not invent one.

**Blocked by (documented):** no documented target contract.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:105` — "a projected substitution-timing model, which does not exist"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:323` — "No projected substitution timing"

### `M17_GENERATIVE_SIMULATION_LAYER`

*Generative simulation layer — accounting constraints documented, estimand not* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

The evaluation side of the distributional layer is canonical; the generative side is recorded as not started. The registered objective supplies a causal order and seven accounting constraints, and the capability matrix names three constraints enforced nowhere. What is NOT documented is the estimand the simulator is graded on. Mark NEEDS_TARGET_CONTRACT for the estimand; the constraints are documented and may be cited.

**Blocked by (documented):** no documented estimand for the generative layer.

**Proposed dependencies:** `F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:293` — "the *generative* side is `not started`"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:295` — "Constraints not yet enforced anywhere"
* `experiments/player_program/register_program_roadmap.py:115` — ""simulation_causal_order""
* `experiments/player_program/register_program_roadmap.py:121` — ""accounting_constraints""

### `M18_ARCHETYPE_LAYER_TARGET_CONTRACT`

*Archetype layer — registered design, unnamed target statistic* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

player_archetype_discovery_layer is a registered research layer with authorises_execution=False, a bounded challenger set, leakage rules, a stability reporting list and an explicit bar. The target statistic it must improve is written only as 'player-event forecasts'. Mark NEEDS_TARGET_CONTRACT for the estimand; the design constraints are documented and binding.

**Blocked by (documented):** registered with authorises_execution=False; start boundary: not before projected_player_possessions_v1 is frozen (satisfied).

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/register_program_roadmap.py:154` — ""experiment_id": "player_archetype_discovery_layer""
* `experiments/player_program/register_program_roadmap.py:156` — ""authorises_execution": False"
* `experiments/player_program/register_program_roadmap.py:243` — ""start_boundary""
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:230` — "the registered archetype layer"

### `M19_LINEUP_CHEMISTRY`

*Lineup chemistry and pairings — future track, no target* — lane `player_targets`, type `documentation`, documented target **ABSENT**, **NEEDS_TARGET_CONTRACT**.

Registered as a preserved future track with a shrinkage/minimum-support constraint and a list of things to test. No estimand, denominator, metric or comparison is stated. Mark NEEDS_TARGET_CONTRACT.

**Blocked by (documented):** no documented target contract.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:232` — "lineup chemistry and pairings"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:234` — "Registered as a future track in"
* `experiments/player_program/register_program_roadmap.py:299` — ""lineup_chemistry_and_transitions""

---

## 8. Proposed nodes — event channels

All five are barred by the stop boundary's *begin another event channel* prohibition, and all five have a documented denominator candidate and no documented estimand.

| id | title | target | NTC | fit? | gate |
|---|---|---|---|---|---|
| `C10_OPPORTUNITY_DENOMINATOR_FRAMEWORK` | Per-channel opportunity-denominator contract framework (wave P0) | DOCUMENTED | no | no | - |
| `C11_REBOUND_CHANNEL` | Rebound channel — denominator named, estimand not; and rebound_type is unresolved | PARTIAL | **yes** | no | - |
| `C12_STEAL_CHANNEL` | Steal channel — attribution differs structurally across the two source schemas | PARTIAL | **yes** | no | - |
| `C13_BLOCK_AND_RIM_CHANNEL` | Blocks and rim events — attribution documented as weakly supported | PARTIAL | **yes** | no | - |
| `C14_ASSIST_CHANNEL` | Assists — the ideal denominator is documented as absent from the data | PARTIAL | **yes** | no | - |
| `C15_FOUL_AND_FREE_THROW_CHANNEL` | Fouls and free throws — free-throw outcome is supplied by neither source | PARTIAL | **yes** | no | - |

### `C10_OPPORTUNITY_DENOMINATOR_FRAMEWORK`

*Per-channel opportunity-denominator contract framework (wave P0)* — lane `player_targets`, type `documentation`, documented target **DOCUMENTED**.

The event-schema blocker is cleared; what remains per channel is a registered opportunity-denominator contract. Write the framework the registered objective's P0 wave describes — event definition, opportunity denominator, prediction requirement, scoreability, cutoff, outcome isolation, baseline metric, conservation constraints — and the rule that a weaker proxy is registered explicitly, never presented as equivalent. Framework only; it authorises no channel.

**Blocked by (documented):** stop boundary: begin another event channel.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:183` — "per-channel opportunity-denominator contracts"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:187` — "None of the six granular channels"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:319` — "Opportunity denominators do not exist"
* `experiments/player_program/register_program_roadmap.py:86` — ""wave_process_per_target""

### `C11_REBOUND_CHANNEL`

*Rebound channel — denominator named, estimand not; and rebound_type is unresolved* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

The documented denominator is rebound opportunities, not total possessions, and the documented blocker is that neither source types offensive-versus-defensive structurally (rebound_type unresolved on all 125,309 rebound rows). No estimand or metric is written. Mark NEEDS_TARGET_CONTRACT.

**Blocked by (documented):** stop boundary: begin another event channel; rebound_type unresolved in both sources.

**Proposed dependencies:** `C10_OPPORTUNITY_DENOMINATOR_FRAMEWORK`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:196` — "rebound opportunities**, not total possessions"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:182` — "`rebound_type` (unresolved on all 125,309 rebound rows)"
* `HANDOFF_TURNOVER_DISCOVERY.md:148` — "`rebound_type` is `unresolved` on all 125,309 rebound rows"

### `C12_STEAL_CHANNEL`

*Steal channel — attribution differs structurally across the two source schemas* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

Steals are recorded as not started, with a documented denominator (per defensive possession) and a documented obstruction: steal/block/assist attribution differs structurally across the two stores and counts are not comparable without a registered linkage rule. No estimand is written. Mark NEEDS_TARGET_CONTRACT.

**Blocked by (documented):** stop boundary: begin another event channel; no registered cross-store linkage rule.

**Proposed dependencies:** `C10_OPPORTUNITY_DENOMINATOR_FRAMEWORK`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:195` — "steals `not started`"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:182` — "steal/block/assist counts ACROSS stores without a registered linkage rule"
* `HANDOFF_TURNOVER_DISCOVERY.md:151` — "Steal/block/assist attribution differs structurally"

### `C13_BLOCK_AND_RIM_CHANNEL`

*Blocks and rim events — attribution documented as weakly supported* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

Documented denominator: blockable opponent attempts / rim attempts. Documented limitation: rim-defence attribution is weakly supported because PLAYER3 credits the blocker only. No estimand is written. Mark NEEDS_TARGET_CONTRACT.

**Blocked by (documented):** stop boundary: begin another event channel.

**Proposed dependencies:** `C10_OPPORTUNITY_DENOMINATOR_FRAMEWORK`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:197` — "blockable opponent attempts / rim attempts"

### `C14_ASSIST_CHANNEL`

*Assists — the ideal denominator is documented as absent from the data* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

Documented: true 'potential assists' are NOT in this data and a weaker proxy must be registered explicitly. CDN supplies no assist attribution at all. No estimand is written. Mark NEEDS_TARGET_CONTRACT.

**Blocked by (documented):** stop boundary: begin another event channel; potential assists absent from the data.

**Proposed dependencies:** `C10_OPPORTUNITY_DENOMINATOR_FRAMEWORK`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:198` — "a weaker proxy must be registered explicitly"
* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:317` — "CDN supplies no incoming substitute and no assist attribution"

### `C15_FOUL_AND_FREE_THROW_CHANNEL`

*Fouls and free throws — free-throw outcome is supplied by neither source* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

Documented denominators: fouls per defensive possession; FT makes conditional on projected attempts. Documented blocker: free-throw outcome is supplied by neither store, and a registered erratum records it as unsupported. Officiating priors exist and are reusable. No estimand is written. Mark NEEDS_TARGET_CONTRACT.

**Blocked by (documented):** stop boundary: begin another event channel; free-throw outcome absent from both sources.

**Proposed dependencies:** `C10_OPPORTUNITY_DENOMINATOR_FRAMEWORK`, `A14_REFEREE_ASSIGNMENT_CUTOFF_VERIFICATION`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:199` — "fouls per defensive possession; FT makes conditional on projected attempts"
* `HANDOFF_TURNOVER_DISCOVERY.md:150` — "Free-throw **outcome** is supplied by neither source"

---

## 9. Proposed nodes — possession research directions the graph does not carry

The program's own ranked-first and ranked-second remaining opportunities. Target-contract drafts only.

| id | title | target | NTC | fit? | gate |
|---|---|---|---|---|---|
| `T10_TEAM_POSSESSION_PRIOR_TARGET_CONTRACT` | Team-possession-total projection — the program's own ranked-first remaining opportunity | DOCUMENTED | no | no | - |
| `T11_GATED_ROLE_EXPANSION_TARGET_CONTRACT` | Preregistered gated role-expansion challenger — ranked second, formulation-dependent | DOCUMENTED | no | no | - |

### `T10_TEAM_POSSESSION_PRIOR_TARGET_CONTRACT`

*Team-possession-total projection — the program's own ranked-first remaining opportunity* — lane `possession`, type `documentation`, documented target **DOCUMENTED**.

Four documents independently rank improved team-possession-total projection as the clearest remaining team-aggregate opportunity, measured at +0.1033 [0.0833, 0.1244], with an honest prize of 1.2-2.2% of operational MAE. Draft the target contract, the matched-K0 requirement and the cutoff-valid evidence inventory. This node does NOT authorise fitting: the documents say 'if authorised' and PROGRAM_STATE records experiment_currently_authorized=false.

**Blocked by (documented):** PROGRAM_STATE: experiment_currently_authorized = false; must be issued as a versioned specification under RESEARCH_CONTRACT_V1.

**Proposed dependencies:** `P28_PRIMARY_SECONDARY_ORDERING_CONTRACT`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:249` — "The most defensible next substantive step"
* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:210` — "Team-possession-total projection"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:274` — "Team possession-total projection"
* `HANDOFF_TURNOVER_DISCOVERY.md:170` — "the only materially addressable team-aggregate error source"
* `HANDOFF_ADDENDUM_INTEGRITY_WORK.md:92` — "team-possession-total projection is the clearest remaining team-aggregate opportunity"

### `T11_GATED_ROLE_EXPANSION_TARGET_CONTRACT`

*Preregistered gated role-expansion challenger — ranked second, formulation-dependent* — lane `possession`, type `documentation`, documented target **DOCUMENTED**.

Ranked second: a preregistered gated role-expansion challenger, WS1 expanded_role_bounded +0.0265 sd 0.0017, positive in every fold, helping 699 team-games with material expansion and hurting the 2,283 without. The wave summary simultaneously classifies role-transition effects as formulation-dependent rather than disproven. Draft the target contract and the gating rule; do not fit.

**Blocked by (documented):** stop boundary: promote any discovery arm; begin a confirmation experiment.

**Proposed dependencies:** `T10_TEAM_POSSESSION_PRIOR_TARGET_CONTRACT`.

**Authorising citations** (each verified against the exact line):

* `HANDOFF_TURNOVER_DISCOVERY.md:109` — "preregistered gated role-expansion challenger"
* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:220` — "Role-transition and responsibility-transfer effects"

---

## 10. Proposed nodes — audit and capture extensions

| id | title | target | NTC | fit? | gate |
|---|---|---|---|---|---|
| `A10_WS1_REMAINING_ARMS_REGRADE` | Extend the WS1 player-grain no-refit re-adjudication to the remaining WS1 arms | DOCUMENTED | no | no | - |
| `A11_WORKSTREAM_FEASIBILITY_EXTRACTION` | Read-only feasibility extraction for WS2, WS3, WS5 and WS7, resolution factor per workstream | DOCUMENTED | no | no | - |
| `A12_MULTIPLICITY_AND_EFFECTIVE_TRIAL_LEDGER` | Multiplicity framework and an effective-trial ledger, prospective only | DOCUMENTED | no | no | - |
| `A13_EXECUTION_SIDE_LOGGING` | Begin capturing execution-side fields now — historical reconstruction is already blocked | DOCUMENTED | no | no | - |
| `A14_REFEREE_ASSIGNMENT_CUTOFF_VERIFICATION` | Establish whether referee assignments land before the forecast cutoff | DOCUMENTED | no | no | - |
| `A15_GARBAGE_TIME_DEFINITION` | Garbage-time definition — construction rules documented, no target | PARTIAL | **yes** | no | - |

### `A10_WS1_REMAINING_ARMS_REGRADE`

*Extend the WS1 player-grain no-refit re-adjudication to the remaining WS1 arms* — lane `operations`, type `audit`, documented target **DOCUMENTED**.

The player-grain re-adjudication is complete for WS1's primary arm and the documents direct it to be extended to the remaining WS1 arms. No refit: predictions, targets, matched K0 and incumbent survive as frozen bytes. If fold identity, K0 or targets cannot be read from frozen bytes, it is a new experiment and this node HALTS.

**Blocked by (documented):** D-2 recommended Approve; owner John; acknowledgment not recorded.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:269` — "extend to the"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:302` — "WS1 no-refit audit"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:319` — "No refit disguised as audit"

### `A11_WORKSTREAM_FEASIBILITY_EXTRACTION`

*Read-only feasibility extraction for WS2, WS3, WS5 and WS7, resolution factor per workstream* — lane `operations`, type `audit`, documented target **DOCUMENTED**.

Read-only feasibility extraction per Appendix D, computing the player-grain resolution factor PER WORKSTREAM. The ~5x factor is scoped to the WS1 turnover surface and the documents forbid generalising it without computing it. Standing constraint: no new metric-based rescoring of closed work. WS2's operational track stays INVALID.

**Blocked by (documented):** D-3 recommended Approve with the standing constraint; owner John.

**Proposed dependencies:** `A10_WS1_REMAINING_ARMS_REGRADE`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:270` — "Read-only feasibility extraction for WS2, WS3, WS5 and WS7"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:303` — "no new metric-based rescoring of closed work"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:328` — "No generalisation of the ~5"

### `A12_MULTIPLICITY_AND_EFFECTIVE_TRIAL_LEDGER`

*Multiplicity framework and an effective-trial ledger, prospective only* — lane `operations`, type `documentation`, documented target **DOCUMENTED**.

Specify a multiplicity framework — Hansen SPA, Model Confidence Set, Romano-Wolf; explicitly NOT Deflated Sharpe, which targets Sharpe ratios on returns — plus an effective-trial ledger counting abandoned formulations, threshold searches, universe changes and analyst-guided reformulations. Research prospectively; do NOT retroactively apply to closed waves.

**Blocked by (documented):** D-5: research prospectively, do not retroactively apply.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:275` — "Multiplicity framework"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:305` — "Research prospectively; do not retroactively apply to closed waves"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:633` — "Hansen SPA, Model Confidence Set, Romano"

### `A13_EXECUTION_SIDE_LOGGING`

*Begin capturing execution-side fields now — historical reconstruction is already blocked* — lane `operations`, type `implementation`, documented target **DOCUMENTED**.

Capture, going forward, the nine named execution-side fields: sportsbook, market, price, timestamp, observable limit, decision label, closing line, executability, slippage. The documents state historical reconstruction is blocked by DL-002 at 27% T-24h coverage, so this is capture infrastructure, not evidence. It creates no historical record and repairs no historical gap.

**Proposed dependencies:** `D11_LIVE_INFORMATION_CAPTURE`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:280` — "Begin capturing execution-side fields now"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:282` — "reconstruction is blocked by DL-002"

### `A14_REFEREE_ASSIGNMENT_CUTOFF_VERIFICATION`

*Establish whether referee assignments land before the forecast cutoff* — lane `data`, type `audit`, documented target **DOCUMENTED**.

The coverage matrix records a hard precondition: referee assignments must be available before the relevant forecast cutoff, the contract's cutoff policy is date-based, the assignment log is a daily capture, and whether assignments land before cutoff is UNVERIFIED. Measure it. D10_FIELD_AVAILABILITY_LEDGER's field list does not name referees, so this is not covered by that node.

**Proposed dependencies:** `D10_FIELD_AVAILABILITY_LEDGER`.

**Authorising citations** (each verified against the exact line):

* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:291` — "Hard precondition, recorded now so it is not discovered late"
* `ROADMAP.md:210` — "usable only if public before the forecast cutoff"

### `A15_GARBAGE_TIME_DEFINITION`

*Garbage-time definition — construction rules documented, no target* — lane `player_targets`, type `documentation`, documented target **PARTIAL**, **NEEDS_TARGET_CONTRACT**.

Two construction requirements are documented: keep BOTH a full-game and a competitive-possession version and do not delete low-leverage possessions; define the rule using only score differential and time remaining, never with reference to the final outcome. No estimand, metric or comparison is documented. Mark NEEDS_TARGET_CONTRACT.

**Blocked by (documented):** no documented target contract.

**Authorising citations** (each verified against the exact line):

* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:296` — "### Garbage time"
* `PLAYER_RESEARCH_COVERAGE_MATRIX.md:300` — "keep **both** a full-game and a competitive-possession version"

---

## 11. Proposed nodes — open methodological gaps recorded in PROGRAM_STATE

Eight gaps are recorded as `implemented: false`. None appears in `PROGRAM_GRAPH.json`. One is Severity A.

| id | title | target | NTC | fit? | gate |
|---|---|---|---|---|---|
| `Q10_FEATURE_PRODUCER_PROVENANCE` | Severity A: only possession_features.py emits a producer construction receipt | DOCUMENTED | no | no | - |
| `Q11_VALIDATOR_LINEAGE` | Validator lineage: the receipt chain is not cryptographically closed | DOCUMENTED | no | no | - |
| `Q12_FRESH_EXECUTION_PROOF` | Fresh execution is not provable: a copied-forward receipt is indistinguishable from a rerun | DOCUMENTED | no | no | - |
| `Q13_CUTOFF_VALIDITY_VERIFICATION` | cutoff_valid is asserted per source and bound into the receipt forever, unverifiable from bytes | DOCUMENTED | no | no | - |
| `Q14_CONSTRUCTION_RECEIPT_FORGERY` | A construction receipt is not a cryptographic attestation | DOCUMENTED | no | no | - |
| `Q15_NONLINEAR_DEPENDENCY_DETECTION` | The gate catches linear rank deficiency only | DOCUMENTED | no | no | - |
| `Q16_PIPELINE_ID_BINDING` | comparison_gate cannot prove K0 came from the challenger's code path | DOCUMENTED | no | no | - |
| `Q17_WS6_FEATURELESS_CONTROL` | WS6 has no K0 of any kind, so its free-intercept confound is uncontrolled | DOCUMENTED | no | no | - |

### `Q10_FEATURE_PRODUCER_PROVENANCE`

*Severity A: only possession_features.py emits a producer construction receipt* — lane `operations`, type `implementation`, documented target **DOCUMENTED**.

PROGRAM_STATE records general_feature_producer_provenance as Severity A, implemented false, blocking any fitted arm whose feature producer emits no construction receipt. It is scoped, not global: the possession-feature path is receipted and unaffected. This gap sits upstream of P36_IMPLEMENT_ARMS and P38_BLINDED_FIT and appears nowhere in the graph.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:84` — "general_feature_producer_provenance"
* `experiments/player_program/RESEARCH_CONTRACT_V1.md:36` — "Requirements 5 and 7 are **contractually required but not yet fully implemented**"

### `Q11_VALIDATOR_LINEAGE`

*Validator lineage: the receipt chain is not cryptographically closed* — lane `operations`, type `implementation`, documented target **DOCUMENTED**.

validate_turnover_targets.py records the producer hash but not its own. Required: validator source digest; unique validation-run ID; exact input manifest; output receipt bound to both; producing commit or environment identity. Severity B.

**Proposed dependencies:** `I13_REPRODUCIBILITY_RUNNER`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:183` — "Validator lineage is incomplete"

### `Q12_FRESH_EXECUTION_PROOF`

*Fresh execution is not provable: a copied-forward receipt is indistinguishable from a rerun* — lane `operations`, type `implementation`, documented target **DOCUMENTED**.

fresh_execution_not_proven fires only on positive duplication evidence and never asserts that validation did not run. Closing it needs a validator-emitted per-execution nonce. Severity B.

**Proposed dependencies:** `Q11_VALIDATOR_LINEAGE`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:188` — "Fresh execution is not provable"

### `Q13_CUTOFF_VALIDITY_VERIFICATION`

*cutoff_valid is asserted per source and bound into the receipt forever, unverifiable from bytes* — lane `operations`, type `audit`, documented target **DOCUMENTED**.

PROGRAM_STATE records cutoff_validity_asserted as Severity B, implemented false: cutoff_valid is a property of upstream construction and cannot be verified from bytes. This is the same class of claim D10_FIELD_AVAILABILITY_LEDGER audits at field level, but here it concerns the receipt binding, not the field ledger.

**Proposed dependencies:** `D10_FIELD_AVAILABILITY_LEDGER`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:86` — "cutoff_validity_asserted"

### `Q14_CONSTRUCTION_RECEIPT_FORGERY`

*A construction receipt is not a cryptographic attestation* — lane `operations`, type `documentation`, documented target **DOCUMENTED**.

PROGRAM_STATE records construction_receipt_forgery as Severity C, implemented false. Record it for the next contract version; it is explicitly not a reason to halt.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:85` — "construction_receipt_forgery"

### `Q15_NONLINEAR_DEPENDENCY_DETECTION`

*The gate catches linear rank deficiency only* — lane `operations`, type `implementation`, documented target **DOCUMENTED**.

A feature deterministic in others through a nonlinear map still passes. Severity C. Enforcement belongs at the call site: feature_gate.py is frozen and must not be edited.

**Proposed dependencies:** `I12_DESIGN_DEPENDENCY_AUDIT`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:191` — "Nonlinear deterministic dependency"
* `HANDOFF_ADDENDUM_INTEGRITY_WORK.md:109` — "Nonlinear dependency"

### `Q16_PIPELINE_ID_BINDING`

*comparison_gate cannot prove K0 came from the challenger's code path* — lane `operations`, type `implementation`, documented target **DOCUMENTED**.

pipeline_id is asserted, not demonstrated; producer-source digest binding would close it. Severity C. comparison_gate.py is frozen; any binding must be a call-site wrapper.

**Proposed dependencies:** `P26_ARM_SPECIFIC_K0_CONTRACT`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:193` — "`pipeline_id` is asserted, not demonstrated"

### `Q17_WS6_FEATURELESS_CONTROL`

*WS6 has no K0 of any kind, so its free-intercept confound is uncontrolled* — lane `operations`, type `audit`, documented target **DOCUMENTED**.

Appendix D classifies WS6 as NEW_EXPERIMENT_REQUIRED: no prediction artifacts, no featureless control, measured as a diagnostic and never tested as a forecaster. This node records the gap and its consequences for anything citing WS6. It does NOT run the new experiment, which would require preregistration and a matched K0.

**Blocked by (documented):** requires preregistration and a matched K0.

**Proposed dependencies:** `F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT`.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:195` — "uncontrolled in WS6"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:528` — "NEW_EXPERIMENT_REQUIRED"

---

## 12. Proposed nodes — decisions awaiting a ruling

| id | title | target | NTC | fit? | gate |
|---|---|---|---|---|---|
| `N10_PROSPECTIVE_START_RECORD_ACK` | D-1: acknowledge record_idx 3 as the prospective_team_pair_v1 start record | DOCUMENTED | no | no | human |
| `N11_CONDITION_6_ADJUDICATION` | D-6: coordinator ruling on registered promotion-gate condition 6 | DOCUMENTED | no | no | human |
| `N12_PRESERVED_GATE_REPAIR_DISPOSITION` | S2: disposition of the preserved fail-closed gate repair is the team thread's call | DOCUMENTED | no | no | human |
| `N13_TEAM_GATE_RECEIPT_FAIL_OPEN` | The shared team gate gate_receipt.py remains fail-open under the inherited GIT_DIR condition | DOCUMENTED | no | no | human |
| `N14_RATE_MODEL_SENSITIVITY_ARM_REPAIR` | The sensitivity arm of the rate model is unrepaired and needs a new registered revision | DOCUMENTED | no | no | - |

### `N10_PROSPECTIVE_START_RECORD_ACK`

*D-1: acknowledge record_idx 3 as the prospective_team_pair_v1 start record* — lane `governance`, type `decision`, documented target **DOCUMENTED**.

Ruled RESOLVED_BY_EXISTING_CONTRACT and awaiting acknowledgment only. Approving fixes the start of record; it does NOT make the stream gradeable. Delay means the start timestamp gets retro-fitted later.

**Blocked by (documented):** owner John; acknowledgment not recorded.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:301` — "RESOLVED_BY_EXISTING_CONTRACT"

### `N11_CONDITION_6_ADJUDICATION`

*D-6: coordinator ruling on registered promotion-gate condition 6* — lane `governance`, type `decision`, documented target **DOCUMENTED**.

Ruled AMBIGUOUS - requires coordinator ruling. The complete gate is ~4.95-5.25% if condition 6 passes and 0.00% if it fails. Do not infer PASS from identity. This concerns a TEAM-programme instrument (W2-C1 against BENCH-R); the player program records it because its own project update carries the decision, and must not rule on it unilaterally.

**Blocked by (documented):** owner John; team-thread instrument.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:306` — "AMBIGUOUS"
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:490` — "Ruling: `AMBIGUOUS"

### `N12_PRESERVED_GATE_REPAIR_DISPOSITION`

*S2: disposition of the preserved fail-closed gate repair is the team thread's call* — lane `governance`, type `decision`, documented target **DOCUMENTED**.

The preserved uncommitted repair under preserved_uncommitted_d69aa02/ is team-thread material. The player program has not modified it and will not commit it to any team branch. Record the open disposition; do not act on it.

**Blocked by (documented):** team thread owns run_team_oof_v12_2.py.

**Authorising citations** (each verified against the exact line):

* `HANDOFF_PLAYER_MODEL_PROGRAM.md:241` — "commit the preserved fail-closed gate repair"
* `PLAYER_RESEARCH_LEDGER.md:152` — "disposition is the team thread"

### `N13_TEAM_GATE_RECEIPT_FAIL_OPEN`

*The shared team gate gate_receipt.py remains fail-open under the inherited GIT_DIR condition* — lane `governance`, type `decision`, documented target **DOCUMENTED**.

certifies_this_commit can falsely certify when git status was never measured. Recorded as a TEAM-thread action and deliberately not modified from this worktree. This node records the standing cross-thread notice; it changes nothing.

**Blocked by (documented):** team-thread action.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:331` — "The shared team gate `gate_receipt.py` remains fail-open"
* `HANDOFF_TURNOVER_DISCOVERY.md:154` — "`gate_receipt.py` is fail-open (team thread)"

### `N14_RATE_MODEL_SENSITIVITY_ARM_REPAIR`

*The sensitivity arm of the rate model is unrepaired and needs a new registered revision* — lane `possession`, type `implementation`, documented target **DOCUMENTED**.

_build_sensitivity removes Tier B rows from the test frame as well as from history. The documents state the repair requires a new registered revision. Specify the revision; registering and running it is a separate authorisation.

**Blocked by (documented):** requires a new registered revision; registry appends are coordinator-only.

**Authorising citations** (each verified against the exact line):

* `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:329` — "The sensitivity arm of the rate model is unrepaired"
* `HANDOFF_TURNOVER_DISCOVERY.md:154` — "The rate-model sensitivity arm is unrepaired"

---

## 13. Documented work that is already modelled — not re-proposed

| documented item | already modelled as |
|---|---|
| PROJECT_UPDATE 2026-08-04 defect D-a, audit classification of late records | O10_LATE_RECORD_AUDIT_CLASSIFICATION |
| defect D-b, obligation discovery / lead window | O11_OBLIGATION_DISCOVERY_LEAD_WINDOW |
| defect D-c, per-game execution scope | O12_PER_GAME_EXECUTION_SCOPE |
| defect D-d, lead-window execution latency | O13_LEAD_WINDOW_LATENCY |
| defect D-e, entity resolution and cold start | D14_ENTITY_RESOLUTION_AND_COLD_START + O14_OPS_ENTITY_RESOLUTION |
| defect D-f, logout survival | O15_LOGOUT_SURVIVAL + R10_O15_REPORT_REMEDIATION |
| decision D-4, bundled cross-thread amendment (daily_forecast.py per-game scope; forecast_log.py SCHEMA/2) | O16_SHARED_SCHEMA_ADOPTION (human gate) |
| PROJECT_UPDATE §7 item 10, within/between involvement as a forecaster | F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT |
| wave-summary ranked item 3, clean player-allocation proxies | F11_PLAYER_ALLOCATION_ARCHITECTURE |
| PROJECT_UPDATE §7 deferred, staged distributional layer | F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS (partially; the generative machinery is proposed here as M17) |
| PROJECT_UPDATE §7 deferred, decision-time comparison | F14_DECISION_TIME_MARKET_COMPARISON |
| PROJECT_UPDATE §7 deferred, player props last | F16_PLAYER_PROPS |
| V2 halt findings S1-S9 | P22, P23, P24, P25, P26, P27, P2A and P21 |
| PROGRAM_STATE gap dual_frame_audit | closed: implemented=true, closed_by PLAYER_DUAL_FRAME_AUDIT_v2 |
| ROADMAP.md Phase 0.5 clustered inference, sealed results, reproducibility | I10, I11 (+R16), I13 |

## 14. Documented work that is closed

Recorded so the extraction is visibly complete rather than selectively silent.

| item | state | citation |
|---|---|---|
| P-D1 reproducibility gate fail-open | RESOLVED 2026-08-03 at ef0d557, clean_producer/2 | `PLAYER_RESEARCH_LEDGER.md:96` |
| P-D2 played player-games outside the obligation universe (977) | v5 Stage 1 BUILT and validated at ac9958f; misses 977 -> 210, residue audited | `PLAYER_RESEARCH_LEDGER.md:154` |
| P-D3 n_prior_games changes meaning on the cold-start fold | RESOLVED by the same commit; n_prior_games retired for three named fields | `PLAYER_RESEARCH_LEDGER.md:191` |
| S1 core.bare=false on the shared repository | RESOLVED; verified across seven checkouts | `PLAYER_RESEARCH_LEDGER.md:98` |
| Event-schema split between the two play-by-play stores | RESOLVED by canonical_player_events/1, 18/18 | `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md:314` |
| Integrity workstreams A-D (baseline parity, receipt integrity, ledger merge, supersession) | PROGRAM_STATE records integrity_integration = COMPLETE | `experiments/player_program/PROGRAM_STATE.json state_of_play.integrity_integration` |

## 15. Contradictions found

Reported, not reconciled. Frozen bytes govern over prose.

### X1 — severity B

* **Claim A.** PLAYER_RESEARCH_LEDGER.md:56 - 'Player artifacts that exist: **None.** experiments/cbs_v14_player_oof/ does not exist. There is no player forecast anywhere in this repository.'
* **Claim B.** The bytes: experiments/cbs_v14_player_oof/attempt_001 holds 81 files and experiments/cbs_v15_player_oof_v5/attempt_001 holds 75, created by commit 35e6f6f 'v14/v4 control: the first real player OOF artifact, 31/31 receipts PASS'.
* **Disposition.** Not resolved here. Frozen bytes govern over prose. The ledger's later appended sections were updated without correcting section 1, and PLAYER_RESEARCH_COVERAGE_MATRIX.md still marks every target BUILT-U (unrun). Proposed node M11 adjudicates it.

### X2 — severity B

* **Claim A.** PLAYER_RESEARCH_COVERAGE_MATRIX.md:235 gates RAPM behind a passing player baseline suite and possession reconciliation, and lists eight required validations, seven ABSENT.
* **Claim B.** PLAYER_MODEL_CAPABILITY_MATRIX.md:215 - P3 next dependency is '**none authorised.** P3 work is stopped.'
* **Disposition.** Not resolved here. One document queues the work, the other closes it. Proposed node M22 records the disagreement rather than picking a side.

### X3 — severity C

* **Claim A.** HANDOFF_PLAYER_MODEL_PROGRAM.md:190-208 gives an order of work in which generating cbs_v14_player_oof is step 2 and scoring authorisation is step 4.
* **Claim B.** PREDICTION_CONTRACT_V5_SPEC.md:292 places generation inside 'Stage 2 - the unchanged v14 model (not yet authorised)'.
* **Disposition.** The two are compatible in sequence but disagree about which authorisation governs generation. Recorded, not resolved.

### X4 — severity C

* **Claim A.** This node's declared read scope in PROGRAM_GRAPH.json is 'experiments/player_program/' only.
* **Claim B.** This node's own generated brief directs it to start with ROADMAP.md, START_HERE.md, MISSION_LEDGER.md, PLAYER_RESEARCH_LEDGER.md, PLAYER_RESEARCH_COVERAGE_MATRIX.md and the three HANDOFF documents, all of which sit at the worktree root, outside that scope.
* **Disposition.** Read anyway, because the brief is the node's instruction and the reads are read-only. Flagged so the contract can be corrected rather than the reads being hidden.

## 16. Stop conditions

* not triggered — a finding would change the primary target, the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set or the leakage status
  * No proposed item alters any of these. The items that touch the candidate universe (M11, M24) are adjudication and inventory nodes and are explicitly barred from changing it.
* **TRIGGERED** — Severity A gap discovered that blocks fitted work
  * general_feature_producer_provenance is recorded in PROGRAM_STATE as Severity A, implemented=false, and blocks any fitted arm whose feature producer emits no construction receipt. It appears in no PROGRAM_GRAPH node, yet P36_IMPLEMENT_ARMS and P38_BLINDED_FIT are fitting nodes. Raised as Q10, not resolved inside this node.

## 17. What this node could not establish

* Whether the 81 files under experiments/cbs_v14_player_oof/attempt_001 were produced under contract v4 or v5, and under which authorisation. Establishing it requires reading fold receipts and manifests, which risks performance peeking; the node prohibition on inspecting comparative historical performance was honoured and the question is handed to M11.
* Which of the Stage C/D/E denominators in the registered objective the program considers settled versus illustrative. register_program_roadmap.py:59 labels them 'examples' and supplies a weaker-proxy rule, so no per-channel denominator was treated as a frozen contract.
* The current status of every proposed item against GRAPH_EVENTS.jsonl. GRAPH_STATE.json is derived from events and the seed statuses in PROGRAM_GRAPH.json are documented as a starting point only; no proposed item carries a status claim.
* Whether MISSION_LEDGER.md carries player-program commitments beyond the standing scoring escalation. It is the team thread's append-only record; it was searched for player-program anchors and only the escalation and the five-arm council scope matched. Team-thread items are recorded as cross-program, never proposed as player-program nodes.
* Any figure describing how well anything performs. No comparative performance was read; SEALED_RESULTS was not opened.

---

*Machine-readable companion: `ROADMAP_EXTRACTION.json`, 42 items, 13 marked NEEDS_TARGET_CONTRACT, 0 carrying authorisation to fit. Source graph sha256 `f502cab51309ad41...`.*
