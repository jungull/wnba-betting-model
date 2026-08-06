# F16_PLAYER_PROPS — TARGET CONTRACT DRAFT

**Node:** `F16_PLAYER_PROPS` · **Lane:** future_research · **Type:** documentation
· **Severity on failure:** C · **Role:** read-only research scout
· **Written:** 2026-08-06 · **Branch:** `player-model-program` (retry 1)

## Epistemic status of this output

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

---

## 1. The estimand

### `NOT_DERIVABLE_FROM_DOCUMENTATION`

The program record names an activity and states an ordering constraint. It does not state a target
statistic, a unit, or a denominator, and this draft does not invent one.

**What the documentation actually says.**

| # | citation | verified text |
|---|---|---|
| E1 | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:284-285` | "**Deferred.** Staged distributional layer; decision-time comparison; player props last, and not before the market premise is evidenced." |
| E2 | `experiments/player_program/orchestration/reports/ROADMAP_EXTRACTION.json` `already_modelled` | `{"documented_item": "PROJECT_UPDATE §7 deferred, player props last", "modelled_as": "F16_PLAYER_PROPS"}` — this is the entire mapping; G04 attached nothing else to this node. |
| E3 | `experiments/player_program/orchestration/DECISION_LEDGER.jsonl` decision `D014_THIRTEEN_TRACKS_HAVE_NO_TARGET_CONTRACT` | "What none of them has is an ESTIMAND: the target statistic, its unit and its denominator... These 13 stay in the graph as documented-but-unfittable, and each needs a target contract, a matched K0, cutoff-valid evidence, a preregistration and an independent gate review before any fit." `F16_PLAYER_PROPS` is listed by name among the 13. |

E1 is the whole of this track's mandate in the program record: an activity name ("player props"),
a position in a sequence ("last"), and a precondition on that position ("not before the market
premise is evidenced" — the same unresolved premise that gates
`F16`'s sibling `F14_DECISION_TIME_MARKET_COMPARISON` and is assigned to node
`P2B_MARKET_ODDS_ELIGIBILITY`, `RUNNING` per `orchestration/GRAPH_STATE.json`). None of that is an
estimand. E3 confirms this reading is the coordinator's own: F16 was named, not overlooked, when the
distinction between "documented activity" and "estimand" was drawn.

### Why an estimand is not merely missing but not yet constructible

1. **No candidate target artifact exists at player grain for the quantities the market actually
   prices.** The only registered player-level target family in this lane is
   `turnover_targets_v1/player_turnover_targets_v1.parquet` (28,328 rows, 32 columns — measured,
   section 3, M0 below): possession-exposure and turnover-subtype counts, denominated per 100
   realised offensive possessions. It contains no `points`, `rebounds`, `assists`, or `threes`
   column of any kind. It was built for a different target (turnovers) and is not a starting point
   for a props estimand as it stands.
2. **The market itself prices four different box-score categories, not one.** Measured directly
   from the live prospective stream (section 3, M1): `player_points`, `player_rebounds`,
   `player_threes`, `player_assists`. A single "player props" estimand is therefore at minimum four
   candidate estimands (one per stat, each needing its own unit and denominator decision — raw
   count vs. per-minute vs. per-possession rate — none of which is written anywhere), not one.
3. **DNP handling is undocumented and is part of the missing estimand, not a side issue.** 15.97%
   of `master_player` rows carry a null `pts` tied to `dnp_reason` (section 3, M5). Whether a
   target treats a DNP as zero, as missing/excluded, or as a graded loss against a posted line is
   an estimand decision. Nothing in the program record makes it.
4. **A related channel with a comparable shape is already registered `NEEDS_TARGET_CONTRACT` for
   the identical reason.** `C11_REBOUND_CHANNEL` documents a denominator ("rebound opportunities,
   not total possessions") with no estimand, and records `rebound_type` as unresolved on **all**
   125,309 rebound rows in both sources (`PLAYER_MODEL_CAPABILITY_MATRIX.md:182,196`). A
   `player_rebounds` prop estimand would need to state whether it targets total rebounds or a
   type-split rebound count; C11's blocker travels with any rebounds-market estimand built later.

**Consequence.** A track with a name, a position in a sequence, and no target statistic is not
closer to fittable than an unregistered one. This track is in that category. It is stated as such
rather than repaired.

---

## 2. The matched-K0 requirement for this target

Stated in full even though the estimand is absent, because it binds whatever a future contract
proposes, and because — unlike a team-level challenger — the current machinery cannot accept a
player-props record at all without an amendment this node has no authority to make.

**The governing contract** is `stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/`. Its terms, as written there:

* `K0_MATCHED` is a **map keyed by `arm_id`**. There is no universal K0; "an arm with no record has
  no authoritative control and cannot be adjudicated" (`P26.../REPORT.md:33-35`).
* `K0_FLAT` is a **diagnostic reference only**; every record must carry
  `k0_flat_role: "diagnostic_only"`, pinned by a schema `const`. Beating `K0_FLAT` has **no
  promotion value** (`REPORT.md:37-40`).
* The matched null holds byte-identical rows, target, folds, weights, offset, fallback machinery,
  nuisance terms and lower-order structural terms — equality on **all seventeen**
  `comparison_gate.DIMENSIONS` (`REPORT.md:43-47`).
* Exclusion minimality: the null excludes **exactly** the declared `treatment_terms` — no more
  (straw control), no less (feature absorption) (`REPORT.md:53-65`).
* **`target` is pinned by the schema with `const: "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"`**
  (`REPORT.md:50`). "A record cannot swap the primary target."

**What this means for player props specifically, beyond what it meant for `F14`.** `F14`'s target
(a possible market-derived team-level feature) could in principle still route through
`K0_MATCHED[arm_id]` against the settled team target, because its candidate treatment terms are
team-level features entering the *existing* pinned target. A player-props estimand cannot: its
outcome variable is not `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS` under any transformation
documented anywhere in this lane. The schema's `const` would have to change to admit a
player-props `K0_MATCHED[arm_id]` record at all. Changing that schema is a change to the
**inference structure**, which is a listed stop-condition trigger for this node and is explicitly
**not this node's decision** — noted here as a fact about the current contract's scope, not
proposed or actioned.

**No `K0_MATCHED[arm_id]` record for any player-props-touching arm exists.** `K0_MATCHED_EXAMPLES.json`
under P26 carries two `EXAMPLE_`-prefixed worked records and states "no real arm exists yet" even
for the settled team target; a fortiori none exists for player props.

**Additional requirement, inherited from the same family as `F14`'s decision-time analysis.** If a
future contract ever pairs a props line against a model projection (rather than treating the
historical box score alone as the target), the pairing is only defined at a named decision-time
label (`T-24h`, `T-8h`, `T-30m` — `ops_lane/O13_LEAD_WINDOW_LATENCY/FINDINGS.json`) with each side
carrying its own observation timestamp proven to precede the same cutoff. Section 3 shows the
retrospective props archive captures **exactly one** snapshot per game — there is no decision-time
label diversity to pair against, so this requirement is unmet by construction on current evidence,
not merely unmeasured.

---

## 3. Cutoff-valid evidence — inventory, not assumption

Read scope for this node is `experiments/player_program/` per `PROGRAM_GRAPH.json`; the two props
data files under `data/props_capture/` and the two masters under `data/masters/` were read because
`measure_props_evidence.py` (this node's own artifact) needs them to answer "does cutoff-valid
props evidence exist," and reading a file to answer that question is not fitting anything, joining
against any sealed result, or reading `stage2b/SEALED_RESULTS/`. Nothing under
`stage2b/SEALED_RESULTS/` was opened. All figures below are **measured**, reproduced live on this
branch immediately before writing this draft (command in section 8 of `REPORT.md`); none is
assumed or carried forward from memory.

### 3.0 Existing player-level target infrastructure (context, not props evidence)

| item | measured |
|---|---|
| `turnover_targets_v1/player_turnover_targets_v1.parquet` | 28,328 rows × 32 columns; columns are possession-exposure, turnover-subtype counts and `turnovers_per_100_off_poss`; **no points/rebounds/assists/threes column of any kind** |

### 3.1 The prospective (witnessed) props stream

| item | value |
|---|---|
| rows | 2,471 |
| distinct API events | 9 |
| distinct snapshots | 5, `20260731T142341Z` .. `20260801T140502Z` |
| markets | `player_points`, `player_rebounds`, `player_threes`, `player_assists` |
| rows by market | points 896, rebounds 602, threes 522, assists 451 |
| distinct player-name strings | 67 |
| `player_id` column present | **false** |
| settlement / result column present | **false** |
| commence range | 2026-07-31T23:30:00Z .. 2026-08-03T00:30:00Z |

### 3.2 The retrospective props archive

| item | value |
|---|---|
| rows | 36,946 |
| games | 784 |
| markets | **`player_points` only** — the other three markets the live stream prices have zero historical rows |
| commence range | 2024-05-14T23:00:00Z .. 2026-07-31T02:10:00Z |
| books | 9 (betrivers, fanduel, williamhill_us, draftkings, betonlineag, bovada, betmgm, fanatics, unibet_us) |
| `player_id` column present | **false** |
| settlement / result column present | **false** |
| distinct requested/returned snapshots per game (max) | **1 / 1** — a single pregame capture per game, not a decision-time series |
| lead time before commence | min 34.4 min, median 69.4 min, max 194.4 min; **0 rows captured after commence** |
| priced players per game | mean 8.37, range 2–14 |

### 3.3 Overlap with the settled modelling universe

Universe: 2,982 team-game rows / 1,491 game clusters (`turnover_targets_v1/team_turnover_reconciliation_v1.parquet`).

| season | team-game rows | rows with any props coverage |
|---|---|---|
| 2021 | 418 | **0** |
| 2022 | 478 | **0** |
| 2023 | 520 | **0** |
| 2024 | 524 | 524 (full) |
| 2025 | 620 | 620 (full) |
| 2026 | 430 | 424 |

All 784 props games that exist fall inside the universe (no props game is outside it), but
retrospective props coverage is **zero for three of the six universe seasons** (1,416 of 2,990
team-game rows, 47.4%, have no props coverage at all) and, even where it exists, covers only the
`player_points` market.

### 3.4 Identity join, archive side

Neither props file carries `player_id`. The identity convention for this lane is an integer
`player_id`, "carried unchanged by every registered player" (`data_lane/D14_ENTITY_RESOLUTION_AND_COLD_START/IDENTITY_AND_COLD_START_CONTRACT.md:18`).
Joining props to `master_player.parquet` is therefore necessarily a normalized-name match, not a
key join.

| item | value |
|---|---|
| priced player-games (archive) | 6,561 |
| matched to a same-game box row by normalized name | 6,420 (**97.85%**) |
| unmatched player-games | 141, across 34 distinct name strings |
| unmatched names whose normalized form exists elsewhere in master | 127 of 141 |
| largest single unmatched name | "Skylar Diggins-Smith" — 70 occurrences |

A 97.85% name-match rate on a normalized-exact join is not a settled linkage procedure; it is a
measured rate with a concentrated residual (one name accounts for half the unmatched rows), and no
document in scope specifies how the residual is to be resolved.

### 3.5 Outcome-column measurability

`master_player.parquet`: 33,712 rows, max `game_date` 2026-07-31. 5,384 rows (15.97%) carry a null
`pts`, all tied to a non-null `dnp_reason`. No document states how a props target would treat these
rows.

### 3.6 Gradeability of the live (prospective) stream today

79 live priced player-games; 31 already have a same-date box row in `master_player` (early-window
overlap), 48 do not because their commence date postdates `master_player`'s coverage horizon
(2026-07-31). This is expected staleness given the masters' refresh cadence, not a data defect, but
it means the live stream cannot be graded until the masters are refreshed past each game's date,
and no cadence guarantee for that refresh is documented in this lane.

**Net.** Real, per-row cutoff-valid props evidence exists only for `player_points`, only for
2024–2026, at one snapshot per game, joined to the player master by name rather than by key. The
other three priced markets, three of six universe seasons, any decision-time series, and any
settlement/outcome column have zero rows of evidence in scope.

---

## 4. Known data blockers

* **B1 — No estimand.** Section 1. `NOT_DERIVABLE_FROM_DOCUMENTATION`; not repaired here.
* **B2 — Explicitly gated behind an open, out-of-node decision.** E1's precondition ("not before
  the market premise is evidenced") ties props to the same unresolved question assigned to
  `P2B_MARKET_ODDS_ELIGIBILITY` (`RUNNING`) that also gates `F14`. Not this node's decision.
* **B3 — The K0 machinery cannot accept a player-props record without a schema change.**
  `K0_MATCHED_SCHEMA.json`'s `target` field is `const`-pinned to
  `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`. Section 2.
* **B4 — No identity key.** Neither props file carries `player_id`; linkage is a normalized-name
  join measured at 97.85%, with an undocumented residual-resolution procedure. Section 3.4.
* **B5 — Three of the four priced markets have zero historical coverage.** Only `player_points` is
  in the retrospective archive; `player_rebounds`, `player_assists`, `player_threes` have no
  historical rows on this branch at all. Section 3.2.
* **B6 — Seasonal coverage gap.** Zero props coverage for 2021–2023 (1,416 of 2,990 universe
  team-game rows). Section 3.3.
* **B7 — Single-snapshot capture; no decision-time diversity.** Max snapshots per game, requested
  and returned, is 1. A decision-time-labelled pairing (section 2) cannot be built from this
  archive as it stands. Section 3.2.
* **B8 — No reusable player-level box-score target artifact.** The one player-level target family
  in this lane (`player_turnover_targets_v1.parquet`) targets turnovers, not points/rebounds/
  assists/threes, and is not a starting point for a props estimand. Section 1, item 1.
* **B9 — Undocumented DNP convention.** 15.97% null `pts`, no stated treatment. Section 3.5.
* **B10 — Rebound-type ambiguity travels with a rebounds-market estimand.** `C11_REBOUND_CHANNEL`
  records `rebound_type` unresolved on all 125,309 rebound rows in both sources
  (`PLAYER_MODEL_CAPABILITY_MATRIX.md:182`). Whether a `player_rebounds` estimand needs total or
  type-split rebounds is undecided upstream of this node.
* **B11 — Live stream is not currently gradeable.** 48 of 79 live priced player-games postdate the
  master's coverage horizon; no refresh-cadence guarantee is documented. Section 3.6.

---

## 5. This draft does not authorise fitting

**This draft does NOT authorise fitting.** It is a target-contract *draft* that concludes the
target contract cannot yet be written. Fitting on this track requires, and does not have:

1. a **target contract** — absent; the estimand is `NOT_DERIVABLE_FROM_DOCUMENTATION` (section 1);
2. a **matched K0** — the requirement is stated (section 2); the schema that would hold it is
   pinned to a different target and no record exists for any player-props arm;
3. **cutoff-valid evidence** — inventoried in section 3; real per-row evidence exists for exactly
   one of four priced markets, for three of six universe seasons, at one snapshot per game, joined
   by name rather than by key;
4. a **preregistration** — none drafted;
5. an **independent gate review** — not this node's, and no verifier has reviewed this draft.

None of the five is in this node's gift. Nothing in this document may be cited as evidence that any
props-derived target is admissible, that any market comparison has been authorised, or that any
estimand has been agreed. No fit was run, no model code was written, no comparative historical
performance was inspected, and nothing under `stage2b/SEALED_RESULTS/` was read.

---

## 6. Why player props stays last — preserving the documented ordering

This draft does not argue for reordering the roadmap; it explains why the ordering it inherited
holds up under measurement.

* **The ordering is explicit and self-conditioning.** E1 places player props last in the same
  sentence that conditions it on an unresolved premise (the market premise, owned by `P2B`,
  `RUNNING`). A track that is contractually deferred behind an open decision cannot be promoted
  ahead of that decision by anything found inside the track itself.
* **The machinery it would need was built for, and proven on, the team target first.** `K0_MATCHED`
  exists, is battle-tested by nine V2 stop-condition findings (S1–S9,
  `stage2a/V2_STOP_CONDITION.json`) and is schema-pinned to
  `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS` — not by oversight but because that is the
  settled primary target this program has spent its effort adjudicating. Extending it to a
  different, player-grain target is new contract work, not a parameter change.
* **The evidence base is measurably the thinnest of the tracks audited in this wave.** One of four
  priced markets has any historical coverage; that coverage starts in 2024, not 2021; there is one
  snapshot per game where `F14`'s comparable requirement needs several; there is no identity key
  where the program's own convention specifies one. Every number is in section 3.
* **What would actually move this track is not more measurement from this node.** It is: (a) the
  market-premise decision at `P2B`, (b) a player-grain extension to the K0 contract, decided by
  whoever owns `P26`/`comparison_gate`, and (c) a props-specific target contract naming a unit and
  denominator per market — none of which this node has the write scope or the mandate to produce.

---

## 7. Stop conditions

**No new stop condition is raised by this node.** One inherited stop condition is restated as open
because it bears directly on this track's precondition (E1):

* **Inherited SC1 (`stage2b/P29_TIP_TIME_AND_COVERAGE_AUDIT/REPORT.md:296-303`), Severity A —
  candidate universe / cutoff-valid feature set.** The market-odds family was excluded on a
  capture-window ground that P29 found contradicted by an archive that predates it. This is the
  same "market premise" E1 makes a precondition for player props. Not resolved here; adjudication
  belongs to `P2B_MARKET_ODDS_ELIGIBILITY`.

Two observations from this node's own measurement are recorded as **informational, not
stop-condition triggers**, because nothing is proposed or changed here:

* The `K0_MATCHED` schema's `const`-pinned `target` field means no player-props K0 record can
  presently exist (section 2). This is a fact about the current contract's scope, not a proposal to
  change it, and it is not this node's decision to make.
* `C11_REBOUND_CHANNEL`'s open `rebound_type` blocker (section 4, B10) would need resolving by
  whichever node owns that channel before a rebounds-market estimand could be written; it is
  restated here as a dependency, not adjudicated.

---

## 8. What I could not establish

* **Whether the 292 `data/odds_capture/historical` snapshots or `data/drive_masters/master_odds.csv`
  carry any player-prop-adjacent structure.** Out of this node's read scope (`data/odds_capture`,
  `data/drive_masters` are not under `experiments/player_program/`); not opened.
* **How the 141 unmatched archive player-games should be resolved.** Whether they are genuine
  non-matches, alternate-spelling variants, or a mix, was not determined beyond the observation
  that 127 of 141 normalized names exist elsewhere in the master under a different game/spelling.
* **Whether any props snapshot has ever been captured at more than one decision-time label for the
  same game.** The retrospective archive's max-per-game snapshot count is 1; whether the live
  capture pipeline (still running) will ever produce more than one label per game was not
  measurable from a five-snapshot window.
* **Any real, graded outcome for a single props line.** No settlement column exists on either props
  file; whether one is computed anywhere downstream of this lane was not established.

---

*Ends. No git command was run. No frozen artifact was edited. Nothing under*
*`stage2b/SEALED_RESULTS/` was read. Nothing was written outside*
*`experiments/player_program/future_research/F16_PLAYER_PROPS/`.*
