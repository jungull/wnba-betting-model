# F12_OFF_DEF_STRENGTH_COMPONENTS — TARGET CONTRACT DRAFT

**Node:** `F12_OFF_DEF_STRENGTH_COMPONENTS` · **Lane:** future_research · **Type:** documentation ·
**Severity on failure:** C · **Role:** read-only research scout
**Governing scientific contract:** `RESEARCH_CONTRACT_V1`
**Branch:** `player-model-program` · **Depends on:** `G04_PROGRAM_ROADMAP_EXTRACTION`

## Epistemic status of this output

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration and an independent gate review.

## THIS DRAFT DOES NOT AUTHORISE FITTING

Stated plainly, and repeated because it is the operative sentence of the document: **nothing in this
draft authorises any fit, any refit, any tuning, any arm registration, or any comparison against a
control.** No model code was written or run for this node. No performance figure of any challenger
was read. `stage2b/SEALED_RESULTS/` was not opened.

Fitting requires all five of: a target contract, a matched K0 for the specific arm, an inventory of
cutoff-valid evidence, a preregistration, and an independent gate review. This document supplies a
*draft* of items one and three and nothing else, and item one comes back **NOT_DERIVABLE**.
Independently, `PROGRAM_STATE.json` `state_of_play.experiment_currently_authorized = false` and
`stop_boundary.in_force = true`.

---

## 1. The estimand

### **NOT_DERIVABLE_FROM_DOCUMENTATION**

There is no documented estimand, target statistic, unit or denominator for "offensive and defensive
strength components" anywhere in `experiments/player_program/`. I did not invent one, and this draft
deliberately leaves the field empty rather than filling it with something plausible.

**The negative, and the proof that the search that produced it works.**

`G04_PROGRAM_ROADMAP_EXTRACTION` catalogued 42 proposed items with citations
(`orchestration/reports/ROADMAP_EXTRACTION.json`, `counts`: 42 proposed, 13 needing a target
contract, 5 human-gated, 33 blocked). The string `F12` occurs **0 times** in that file. The same
scan over the same bytes returns `F10` 2×, `F11` 1×, `F13` 2×, `F14` 1×, `F16` 1× — so the search
resolves sibling node ids correctly and the zero is a real absence, not a failed match. `F15` is
also 0×. Of the seven future-research nodes, five are mapped in G04's `already_modelled` block to a
documented source item; **F12 and F15 are the two that are not.**

Command (run from the worktree root):

```
python -c "import json; d=json.load(open('experiments/player_program/orchestration/reports/ROADMAP_EXTRACTION.json')); s=json.dumps(d); print([(n, s.count(n)) for n in ['F10','F11','F12','F13','F14','F15','F16']])"
# [('F10', 2), ('F11', 1), ('F12', 0), ('F13', 2), ('F14', 1), ('F15', 0), ('F16', 1)]
```

**Where the node's title actually comes from.** It is a title string in the graph seed, with no
documentary parent:

* `experiments/player_program/orchestration/scripts/seed_graph.py:930` —
  `("F12_OFF_DEF_STRENGTH_COMPONENTS", "Offensive and defensive strength components"),`
* propagated to `orchestration/PROGRAM_GRAPH.json:3942` `"title": "Offensive and defensive strength components"`.

The seven `future` entries at `seed_graph.py:927-935` are supplied as `(id, title)` pairs only; the
loop at `:936-948` attaches the same four acceptance criteria and the same epistemic-status string
to all seven. F12 therefore inherits the *form* of a target-contract node without ever having been
given a target.

### What I did find — four documentary anchors, none of them an estimand

**(a) The registered program objective names "team strengths" as an aggregation direction, not a
statistic.** Verified in the registered bytes, `arm_registry.jsonl` **line 17**, record
`experiment_id = player_program_objective_v2`, `kind = program_objective`,
`authorises_execution = false`:

> these forecasts aggregate through the PROJECTED ROTATIONS to construct team strengths and opponent-specific matchup interactions

(also `register_program_roadmap.py:57-58`). This is a direction of travel. It names no statistic, no
unit, no denominator, no metric, no scoring rule and no evaluation universe. The record's only
denominator-shaped key is `natural_opportunity_denominators`, which is per-event-channel
(`register_program_roadmap.py:59-76`) and whose entries `register_program_roadmap.py:63` labels
`"examples"` — G04 recorded in `could_not_establish` that it could not determine which of those are
settled versus illustrative. Nothing there is a team-strength denominator.

**(b) The same registered objective rules out the obvious naive reading.**
`register_program_roadmap.py:47-48` / `arm_registry.jsonl:17` `statement`:

> the intended endpoint is a granular player-event forecasting and game-simulation system. It is not merely a generic RAPM, offensive rating or defensive rating.

So "offensive/defensive strength component" **cannot** be silently resolved to an offensive rating,
a defensive rating, or a RAPM split. The registered objective explicitly disclaims that reading.
This is the single most important reason not to invent an estimand here: the most natural invention
is the one the program has already refused in writing.

**(c) The one existing off/def decomposition is frozen and closed, not a live target.**
`fits_v1/p3_coefficients_v1.parquet` carries `orapm_100` / `drapm_100` / `net_rapm_100`.
`PLAYER_MODEL_CAPABILITY_MATRIX.md:215` reads `next dependency | **none authorised.** P3 work is
stopped.` and `:214` forbids reuse of `individual **defensive** coefficients as interpretable player
ratings`. `:212` records the split verdict: intrinsic positive, **operational null — all five arms
fail under projected exposure**. P3 is not an available estimand for F12; it is a closed track whose
defensive half is explicitly barred from the interpretation F12's title invites.

**(d) The dependency that would make an off/def split meaningful is documented as non-existent, with
no target of its own.** `PLAYER_MODEL_CAPABILITY_MATRIX.md:145`: `a substitution-timing model would
be needed to separate off/def exposure`; `:323` `No projected substitution timing`. G04 catalogued
this as item `M16_PROJECTED_SUBSTITUTION_TIMING`, `documented_target: "ABSENT"`,
`needs_target_contract: true`, with the mandate *"Mark NEEDS_TARGET_CONTRACT; do not invent one."*
F12 sits downstream of an item that is itself estimand-less.

### The consequence, stated in G04's terms

A registered layer with machinery and no estimand is a well-specified procedure with nothing to
grade it against. F12 is one step worse than the 13 items G04 flagged: those at least have a
documented mandate with citations. F12 has a title. **The correct disposition of this node is
NEEDS_TARGET_CONTRACT, referred to a human authorisation step, and this draft neither proposes nor
implies a candidate.**

---

## 2. The matched-K0 requirement for this target

Because there is no target, this section states the requirement that **would** bind any future F12
arm, and the structural obstacle that a future F12 target contract must clear first. It is drawn
entirely from the existing contract; nothing here is new policy.

1. **`K0_MATCHED` is a map keyed by `arm_id`, not a shared object.** Every arm carries exactly one
   record; two arms may not share one; an arm with no record has no authoritative control and cannot
   be adjudicated (`stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/REPORT.md` §1.1).
2. **`K0_FLAT` is diagnostic only.** Beating it has no promotion value; every record must carry
   `k0_flat_role: "diagnostic_only"`, pinned by a schema `const` (P26 REPORT §1.1).
3. **The invariant set.** The matched null holds byte-identical rows (as a digest), target, folds,
   weights, offset, fallback machinery, nuisance terms and lower-order structural terms — enforced
   as equality on all seventeen `comparison_gate.DIMENSIONS` plus a redundant `invariants` pin
   (P26 REPORT §1.2).
4. **Exclusion minimality.** The null excludes *exactly* the declared treatment terms and no more:
   `set(arm.substantive) - set(k0.substantive) == set(T)`, `set(T) ∩ set(k0.structural) == ∅`,
   `set(arm.structural) == set(k0.structural)` (P26 REPORT §1.3). Removing more is a straw control;
   retaining any of `T` is feature absorption.
5. **Structural terms must be declared in `k0_spec.structural_terms`**, never in
   `substantive_features` — the frozen `comparison_gate.k0_findings` blocks any K0 with
   `n_substantive_features > 0` (P26 REPORT §1.4). Enforcement belongs at the call site
   (`validate_k0_matched.py`); the frozen gate is not to be edited.

**The structural obstacle, raised and not resolved.**
`P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_SCHEMA.json:109` pins

```json
"target": {"type": "string", "const": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"}
```

so a `K0_MATCHED` record **cannot name any other target**. Any future off/def strength work is
therefore admissible under the present control structure in exactly one shape: as a **treatment term
inside an arm whose target remains `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`**, with the
matched null differing from the arm only by that term. A free-standing "team offensive strength" or
"team defensive strength" statistic as its own dependent variable has **no representable matched
control today**.

I am raising that as a fact about the current contract, not proposing a change to it. Creating a
second adjudicable target, or a second control structure, would alter the primary target and the K0
structure — a listed stop condition for this node. **HALT: referred upward, not resolved here.**
Note also the frozen downstream mismatch the node brief records: the operational scorer pairs
regulation-equivalent projected exposure with raw full-game turnovers, the scorer is frozen, and
possession candidates are selected on the primary possession target first — downstream results may
never rescue a candidate that fails the primary target.

---

## 3. Cutoff-valid evidence — inventoried, never assumed

Two standing cautions govern every row below, and neither is rhetorical.

* **Availability is not eligibility; eligibility is not admission.**
* `EVIDENCE_PACKET_V2.json` `cutoff_valid_availability_table_CORRECTED.warning`, verbatim: *"this
  table records AVAILABILITY and COVERAGE. It does NOT prove cutoff validity — a construction receipt
  binds that declaration but cannot verify it (PROGRAM_STATE gap `cutoff_validity_asserted`). Each
  entry still requires scientific review before it may back a registered arm."* That gap is recorded
  in `PROGRAM_STATE.json` `open_methodological_gaps` as id `cutoff_validity_asserted`, severity B,
  `implemented: false`.

The packet's rule: *"a field is CUTOFF-VALID only if its value is knowable strictly BEFORE the target
game tips. A realised box-score column is cutoff-valid ONLY as LAGGED history over strictly earlier
games, never for the target game."*

### 3.1 Declared-cutoff-valid fields in the frozen V2 packet

Measured: the packet contains exactly **9** entries carrying a `cutoff_valid` key — 7 with value
`true`, 2 with value `"ONLY LAGGED"`.

```
python -c "import json; d=json.load(open('experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json')); ..."
# entries with cutoff_valid: 9 ; Counter({'True': 7, 'ONLY LAGGED': 2})
```

| field | source | coverage | `cutoff_valid` | bearing on an off/def strength component |
|---|---|---|---|---|
| game_id / team_id / opponent identity | contract schedule | 2990/2990 team-games | `true` | identifies the opponent side of any matchup term |
| game_date, season, season_type | contract schedule | 2990/2990 | `true` | fold and chronology only |
| is_home | `master_team.parquet` | 2990/2990 | `true` | context, not strength |
| days_rest, back-to-back, game_no, density | derived from schedule dates | 2990/2990 | `true` | context, not strength |
| own realised `game_pace`, strictly earlier games | `possessions_raw_v2` | 2982 resolved | `true` | the incumbent's own input; lagged by construction |
| **OPPONENT realised `game_pace`, strictly earlier games** | `possessions_raw_v2` + schedule | 2982 resolved | `true` | **the one genuinely opponent-side cutoff-valid quantity; NOT used by the incumbent** |
| venue, travel distance, elevation, time zone | `data/reference/team_cities.csv` (16 rows) | static reference | `true` (v1 ABSENT verdict withdrawn as coordinator error) | environment, not strength |
| team prior-game box aggregates (fga, fta, oreb, tov, …) | `master_team.parquet` | 2990/2990, 65 cols | **ONLY LAGGED** | 7 cols are schedule/identity; **the other 58 are realised target-game outcomes** and are admissible only over strictly earlier games |
| possession-level `end_reason`, `duration_sec`, `period` | `possessions_raw_v2` | all contract games | **ONLY LAGGED** | realised; lagged use only. Note the standing prohibition on same-game duration/OT surrogates |

### 3.2 Program artifacts that would be inputs, with what I measured on the bytes

| artifact | measured | admissibility |
|---|---|---|
| `fits_v1/p3_coefficients_v1.parquet` | **1,177** rows, **314** distinct `player_id`, cutoffs **2021–2025**; `corr(off_possessions, def_possessions) = 0.99998902`; `corr(orapm_100, drapm_100) = 0.16568`; `net_rapm_100 == orapm_100 + drapm_100` exactly | frozen. Reusable *"for a future ablation only if a materially different exposure artifact is developed for an independently justified reason"* (`CAPABILITY_MATRIX:213`). Defensive coefficients barred as ratings (`:214`). **P3 work is stopped (`:215`).** |
| `projected_exposure_v1/projected_player_possessions_v1.parquet` | **120,262** rows over **1,495** games; `production_eligible = False` on **all 120,262**; `projected_off_possessions == projected_def_possessions` on **all 120,160 non-null rows** (the 102 apparent exceptions are rows where both are null, not rows where they differ); regimes `tier_a_only` 35,629 / `tier_a_plus_tx_b` 39,790 / `tier_a_plus_tx_b_plus_s2` 44,843; `information_available_at_cutoff` True on 80,472 and False on 39,790; `historically_captured_asof` True on only **35,629** | research use only. **Equal off/def possessions is a v1 projection assumption, not a measured player-level fact** (`CAPABILITY_MATRIX:144`; `register_exposure_errata.py:97-98`). It therefore supplies *no* information for separating an offensive from a defensive component. |
| `event_contract_v1/canonical_player_events_v1.parquet` | **589,123** rows × 50 columns (see contradiction C1) | `must not reuse`: steal/block/assist counts across stores without a registered linkage rule; `rebound_type` unresolved on all 125,309 rebound rows; free-throw outcome supplied by neither store (`CAPABILITY_MATRIX:182`) |
| `projected_exposure_v1/team_possession_prior_v1.parquet` (`team_possession_prior/1`) | prior-games-only projected team offensive possessions for 2,982 of 2,990 team-games (documented; not re-derived here) | reusable for any downstream possession need (`CAPABILITY_MATRIX:169`) |

### 3.3 Inventoried as NOT available — the absences that bite hardest here

From the same frozen packet, `unavailable_or_insufficient`:

* **starting lineup / rotation announced pregame — UNAVAILABLE**, source *"no captured pregame
  feed"*; realised lineups are target-game outcomes. This is decisive: a strength component built
  from *projected rotations*, which is what the registered objective's aggregation clause calls for,
  has no pregame rotation feed to stand on.
* **coaching identity, change, tactical scheme — ABSENT**, no source in the repository.
* **referee / official assignments — UNAVAILABLE**, 0 of 1,495 contract games overlap;
  `officials_master.csv` carries no `game_id` join.
* **injury / availability report — UNAVAILABLE HISTORICALLY**, capture runs 2026-07-30..2026-08-04
  only (6 days of a 5-season span).
* **market odds / totals — UNAVAILABLE HISTORICALLY**, capture begins 2026-07-31, after the
  modelling span.
* **injury / transaction history** (`data/injury_history/injury_history.csv`, 8,340 rows,
  2021-01-07..2026-07-29): *availability established, cutoff validity NOT established* — no
  observation timestamp; Category B on cutoff grounds.

---

## 4. Known data blockers

1. **No estimand.** The binding blocker. Everything below is downstream of it.
2. **No projected substitution timing.** Named as the dependency that would separate offensive from
   defensive exposure and recorded as not existing (`CAPABILITY_MATRIX:145`, `:323`; G04 item M16,
   `documented_target: ABSENT`).
3. **Off/def exposure is assumed equal, not measured.** Measured above: equal on all 120,160
   non-null rows. `register_exposure_errata.py:97-98` records that substitutions occur *between*
   possessions, so an individual player's realised offensive and defensive possession counts are not
   identical — the artifact's equality is a modelling assumption the errata explicitly refuses to
   promote to a fact.
4. **Off/def identifiability, measured.** `corr(off_possessions, def_possessions) = 0.99998902` on
   the P3 rows; the capability matrix records design rank deficiency 2 and defensive penalties
   selected 3–10× larger. `possessions_v1/POSSESSION_INTEGRITY_RECEIPT.json:671`: *"a full-rank-looking
   matrix is not an identified model. Separate offensive and defensive player effects are identifiable
   ONLY under explicit constraints"* — every possession carries exactly five offensive and five
   defensive indicators, so each block's row sums are constant and each block is collinear with the
   intercept. **A separate offensive and defensive decomposition is not identified without a
   registered constraint, and no such constraint is registered.**
5. **No pregame lineup or rotation feed** (§3.3), which is what the registered aggregation clause
   would need.
6. **Cutoff validity is asserted, never verified** — `PROGRAM_STATE` gap `cutoff_validity_asserted`,
   severity B, `implemented: false`. Every `cutoff_valid: true` in §3.1 is a declaration.
7. **Feature-producer provenance is incomplete** — `PROGRAM_STATE.provenance_status.general_feature_producer_provenance = "incomplete"`; only `possession_features.py` emits a producer construction receipt. G04 raised this as `Q10` and recorded the stop condition *"Severity A gap discovered that blocks fitted work"* as **triggered**. Any future F12 feature producer inherits that blocker.
8. **The primary target is settled and the prohibition list is live.** Current-game realized
   overtime, `game_minutes`, duration, overtime periods and any exact or approximate same-game
   surrogate are prohibited from the prediction path. Several strength-flavoured constructions
   (pace-per-48, per-regulation-minute ratings) walk straight into that prohibition.
9. **Program-level authorisation is absent.** `experiment_currently_authorized = false`;
   `stop_boundary.in_force = true`.

---

## 5. Contradictions found

**C1 — canonical event row count, document versus bytes (severity C).**
`PLAYER_MODEL_CAPABILITY_MATRIX.md:181` and `:33`, and `event_contract_v1/EVENT_CROSSWALK.md:3` and
`EVENT_LIMITATIONS.md:3`, describe the canonical stream as **589,130** rows. The parquet holds
**589,123** rows (`pd.read_parquet(...); len(df) == 589123`). The receipt itself keeps the two
apart: `EVENT_NORMALISATION_RECEIPT.json:26` `"canonical_rows": 589123`, `:28` `"raw_total": 589130`,
`:40` `"canonical_total": 589123`; `EVENT_VALIDATION.json:96,119,131,152,331,374` all say 589123.
Frozen bytes govern over prose: **589,123 canonical rows, 589,130 raw source events.** The prose
documents have collapsed the two numbers. Reported, not repaired — the files are outside this node's
write scope.

**C2 — a graph node with no documentary parent (severity C).**
`PROGRAM_GRAPH.json` schedules F12 with the full acceptance criteria of a target-contract node, and
G04's roadmap extraction — the node's sole declared dependency — contains no item it corresponds to
(0 occurrences of `F12`, against 2/1/2/1/1 for F10/F11/F13/F14/F16, and 5 of 7 future nodes mapped
in `already_modelled` while F12 and F15 are not). Either a documented item exists that G04 missed,
or the node was seeded from a title alone. On the bytes I can read, it is the second. Recorded, not
resolved.

*(For completeness, G04 already recorded contradictions X1–X4; none of them bears on F12 and I have
not re-litigated them.)*

---

## 6. What I could not establish

* **Any estimand for this node.** Not established, and deliberately not invented. See §1.
* **Whether "offensive and defensive strength components" was ever intended as a distinct research
  item, or is a restatement of the registered objective's aggregation clause.** No document
  distinguishes them; `seed_graph.py:930` supplies the title with no citation.
* **Whether the 58 realised box columns in `master_team.parquet` could support a lagged
  opponent-strength construction that survives review.** Availability is documented (2990/2990);
  cutoff validity is asserted, not verified (gap `cutoff_validity_asserted`); and admissibility is a
  scientific-review question this node has no standing to answer.
* **Any figure describing how well anything performs.** No comparative performance was read; the
  operational-null verdict quoted in §1(c) is a documented *direction* already public in the
  capability matrix, not a performance measurement taken by this node.
* **Whether `team_possession_prior_v1.parquet` reproduces its documented 2,982/2,990 coverage.** I
  read the file list but did not re-derive the coverage figure; the number in §3.2 is documentary,
  and is labelled as such.

---

## 7. Stop conditions

| stop condition | tripped | note |
|---|---|---|
| a finding would change the primary target, the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set or the leakage status | **RAISED, not resolved** | §2: `K0_MATCHED_SCHEMA.json:109` pins the target with a `const`, so a free-standing off/def strength statistic has no representable matched control. Creating one would change the primary target and the K0 structure. Referred upward; nothing changed here. |
| (inherited, from G04) Severity A gap blocking fitted work | **already triggered upstream** | `general_feature_producer_provenance`, `implemented: false`, raised by G04 as Q10. Restated here because any future F12 producer inherits it. |

Nothing frozen was edited. No git command was run. Writes are confined to
`experiments/player_program/future_research/F12_OFF_DEF_STRENGTH_COMPONENTS/`.

---

## 8. Recommended disposition

`NEEDS_TARGET_CONTRACT` — human authorisation step. If the program wants an offensive/defensive
strength component, the estimand must be written by whoever owns the objective, and it must clear
four things this node has measured as open: the registered objective's own disclaimer of ratings-like
targets (§1b), the identifiability constraint (§4.4), the absence of substitution timing (§4.2), and
the `const`-pinned K0 target (§2). Until then, F12 has machinery and no estimand, which is the exact
condition G04 named — and a well-specified procedure with nothing to grade it against is not closer
to fittable than no procedure at all.
