# `identity_and_cold_start/1` — declared behaviour at the entity and history boundaries

**Epistemic status:** DESIGN ARTIFACT + TESTS. Defines behaviour at the boundaries. Establishes no
effect.

**Node:** `D14_ENTITY_RESOLUTION_AND_COLD_START` (data lane).
**Nothing here is fitted, scored, tuned or promoted.** Every clause is either (a) a restatement of
behaviour already present in the bytes and pinned by a test in `TESTS.py`, or (b) an explicitly
labelled **REQUIREMENT** that is *not* currently met and must not be assumed.

This document does not amend `PREDICTION_CONTRACT_V5_SPEC.md`, which governs. Where the two
disagree, the disagreement is recorded here and in `REPORT.md` rather than reconciled.

---

## 1. What "identity" is in this program

The person key is an **integer `player_id`**, carried unchanged by every registered player
artifact. There is **no free-text player-name column anywhere** in
`projected_player_possessions_v1`, `player_turnover_targets_v1` or
`player_season_possessions_v2` (test **A1**). Consequently:

> **The classical alias problem — two spellings of one person — cannot arise inside this program's
> artifacts. It arises only at the ingest boundary, where a name-keyed source is joined to an
> id-keyed universe, and every one of those sources lives outside this node's read scope.**

The name→id resolution therefore has to be evidenced at the boundary, not here.
`ROSTER_SOURCE_AUDIT_RECEIPT.json` is that evidence and it is quoted, not re-measured, in §6.

## 2. The four actor classes in the event stream

`canonical_player_events/1` carries a **polymorphic** actor column. `player1_id` holds one of four
entity classes depending on `event_family` (test **A3**, measured over 574,295 non-null values):

| class | distinct ids | rows | share of non-null `player1_id` | families |
|---|---:|---:|---:|---|
| **universe player** | 381 | 532,265 | 92.68% | all |
| **team** (a `team_id` in the person field) | 15 | 38,726 | 6.74% | rebound 23,131 · timeout 12,227 · turnover 2,803 · violation 520 · foul 45 |
| **official-shaped** (ids 7–824) | 629 | 3,117 | 0.54% | `replay_or_administrative` only |
| **non-roster person** (id ≥ 100000, not in the universe) | 39 | 187 | 0.03% | foul 180 (64 explicitly `Technical`) · ejection 7 |

`player3_id` shows the same team-in-person-field behaviour on 13 ids over 172 rows.
`player2_id` is clean: 305 ids, all resolving to universe players.

**Declared rule.** Any consumer joining an event to a player identity **must** classify the actor
before joining:

```
actor_class(player1_id) =
    "team"              if player1_id in master team ids
    "official"          if player1_id < 100000
    "non_roster_person" if player1_id >= 100000 and player1_id not in the player universe
    "player"            otherwise
```

A join that omits this step silently attributes 7.32% of actor-bearing event rows to a player who
does not exist. **A bare `player1_id` join is prohibited in any feature construction.**

**Precedent that this rule is achievable.** `player_turnover_targets/1` already applies it: the
2,803 team-actor turnover events appear as `team_unattributed` in
`team_turnover_reconciliation_v1`, **exactly**, and are never charged to a player
(test **A4**: 2,803 = 2,803; 39,278 player-attributed of 42,081 total). The rebound, timeout,
violation and foul classes have **no equivalent handling declared anywhere**.

## 3. Team transitions

**A transfer is one `player_id` carrying two `team_id`s.** It is never a new identity. Measured on
realised play: **82 of 1,039 player-seasons** involve more than one club (75 with two, 7 with
three), and the registered per-player-season count is exactly reproducible from the raw possession
lineups (test **B1**).

**Dual obligation is retained and is not a duplicate.** At the forecast cutoff the contract cannot
know a player has moved, so both clubs owe an obligation. Measured: **616 distinct (player, game)
pairs across 147 players and 153 games are claimed by exactly two clubs**, yielding 1,232
distinctly keyed obligations, never three (test **B2**). The flag
`candidate_claimed_by_multiple_teams` is exactly the >1-club condition, with zero disagreements
(test **B3**).

**Multi-club candidacy must always be reported per tier.** Blending the tiers misdescribes
transitions by a factor of five (test **B4**):

| tier | player-seasons | with >1 club | max clubs in one season |
|---|---:|---:|---:|
| A (verified, S1/S3) | 1,058 | 91 (8.6%) | 3 |
| B (S_TX / S2) | 1,496 | 678 (45.3%) | **7** |

Tier A's 8.6% is close to the realised 7.9% (82/1,039). Tier B's 45.3% and its seven-club maximum
are **candidate inflation, not transfers**, and any statement about "how often players change
teams" computed over A∪B is wrong.

### REQUIREMENT T-1 — not currently met

`PREDICTION_CONTRACT_V5_SPEC.md` §3 defines `is_cold_start` as *"no prior appearance for **this
team** this season."* The bytes implement **player-season**, not player-team-season. **75
obligations** are a player's debut for a new club while she already has season history at another
club, and **all 75 carry `is_cold_start = False`** (test **B5**; 60 distinct players; 31 Tier A,
44 Tier B; present in all six seasons). A team-transition debut is the archetypal cold start and
the flag does not fire on it. Either the field or the spec must move; this node does not choose.

## 4. The cold-start ladder — two orthogonal axes

The single most important structural fact measured by this node:

> **"Cold start" is two different questions, and the artifact answers both with the same word.**

| axis | question | field | fires on |
|---|---|---|---|
| **player history** | has *this player* appeared before? | `is_cold_start` | 8,300 of 44,843 obligations (18.5%) |
| **fold degeneracy** | does *this fold* have a prior season to fit on? | `fallback_level == 4` | 4,989 obligations — **exactly all of season 2021, and nothing else** |

Test **C5**: level 4 fires on 4,989 of 4,989 season-2021 obligations, on zero rows in any other
season, identically for both targets, and **13,944 of the level-4 rows have
`is_cold_start = False`** with a median of 12 prior appearances. A player with a full season of
history receives a fallback prediction because the *model* has no history, not because she does.
Conflating the two axes would attribute a fold artefact to player novelty.

### Declared ladder behaviour (what the bytes do)

| level | `p_active` | `e_minutes_given_active` |
|---:|---:|---:|
| 0 (fitted) | 35,362 | 28,009 |
| 2 | 2,638 | 3,675 |
| 3 | 1,854 | 8,170 |
| 4 (2021 fold) | 4,989 | 4,989 |

*(counts over the 44,843 distinct obligations)*

**The two targets key their cold start on different questions and must not be collapsed**
(test **C6**). Outside the degenerate fold, **4,501 cold-start obligations keep a fitted
`p_active`** — a candidate with prior obligations but no appearance is informative about
availability (median 3 prior team games) — while **zero cold-start obligations keep a fitted
`e_minutes_given_active`**. Availability keys on prior *obligations*; conditional minutes keys on
prior *appearances*. This is the P-D3 defect's intended repair and it is present in the bytes.

### Declared non-silence rules (all currently met)

* **C2** — every zero-history obligation carries `e_min_fallback_level > 0`. Zero exceptions over
  8,300 rows. No cold-start row is served by the fitted estimator in silence.
* **C3** — `is_fallback` and `fallback_level` agree in both directions on both targets, and
  `pred_is_fallback` is exactly their disjunction. Zero disagreements over 44,843 rows.
* **C4** — all 17 identity/cold-start declaration fields are present and non-null on every
  obligation. Zero nulls. **A null in any of these fields is by definition a silent default and
  fails this contract.**
* **C8** — a cold-start obligation still receives a finite, non-negative minutes projection
  (max 40.0). Where a downstream quantity cannot be formed it is **null with a declared reason**:
  51 obligations carry `projected_off_possessions = NULL` and every one of them carries
  `team_game_status = minutes_only_no_pace` **and** `pace_source = unresolved_no_prior_games`.
  That is the *team-level* cold start — a club with no prior games has no pace estimate — and it
  is declared rather than imputed.

### REQUIREMENT C-1 — the ladder rule is not reconstructible from the emitted fields

Level 3 implies `n_prior_appearances <= 1`, but the converse fails: of the 1,898 ex-2021
obligations with exactly one prior appearance, **1,697 sit at level 2 and only 201 at level 3**
(test **C7**). The switch depends on something the artifact does not emit. The producing code
(`cbs_v15`) is outside this node's read scope. **The ladder's numeric rule is therefore UNDECLARED
in every artifact a consumer can read**, and any document asserting a threshold is asserting
something the bytes do not support.

### REQUIREMENT C-2 — `n_prior_appearances == 0` does not mean "never played"

`n_prior_appearances` counts **admitted** prior appearances. Where an earlier appearance was a
candidate-universe miss it does not increment. Measured against realised box membership
(test **C9**, postgame audit only, permitted by spec §6): **474 of 28,107 audited obligations
(1.69%) carry a counter exactly one below the realised count**, in that direction on every single
one. The resulting false-cold-start rate is small but non-zero: **2 obligations are flagged cold
start while the player had in fact already played that season** (2023 and 2024, one player each).

Any consumer treating `is_cold_start` as a fact about the player rather than about the *universe*
is wrong on those rows. It is a statement about admitted evidence.

## 5. Zero-history admission — new signings

A player with no prior box row for anyone can enter the universe only through a source that names
her before she plays.

| source | tier | rows | can create a zero-history obligation |
|---|---|---:|---|
| S1 in-season box membership | A | 106,881 assignments | no — requires a prior box row |
| S3 captured availability report | A | **18** | **yes**, and it is the only Tier A route |
| S_TX transaction wire | B | 8,322 | yes, but Tier B only |
| S2 prior-season affiliation | B, weak | 5,053 | yes, but Tier B only, and it cannot see a rookie |
| S4 timestamped official feed | A | **0 — RESERVED, DECLARED UNAVAILABLE** | — |

S3 admits **18 obligations across 18 distinct players on 2026-07-30 and 2026-07-31**, of which
**1 is a cold start** (test **D3**: no S3 admission exists before 2026-07-30, as the era rule
requires). Tier integrity holds absolutely (test **D1**): Tier A is assigned only by S1 or S3,
Tier B only by S_TX or S2, and the token `S4` appears in no `candidate_source` value anywhere.
`team_assignment_source` determines `team_assignment_confidence` and `roster_evidence_regime`
one-to-one, with no exceptions (test **D2**), so an operator cannot read "verified" off a
retrospectively scraped source.

**Cold start by tier is therefore extremely uneven and must never be pooled:**

| tier | obligations | cold start | rate |
|---|---:|---:|---:|
| A | 35,629 | 1,280 | 3.6% |
| B | 9,214 | 7,020 | **76.2%** |

## 6. The structural full-team cold start

The candidacy floor is not a player property at all. **Every club's season opener has zero Tier A
candidates** — 76 team-games, distributed 12·12·12·12·13·15 across 2021–2026, exactly the league
size each season, all Regular Season (test **D4**). Each is declared
`unresolved_insufficient_candidates` with `n_candidates = 0` and `n_allocated = 0`. **No rotation
is manufactured.**

Adding the weak evidence tiers resolves 74 of the 76. **Two remain unresolved under the widest
evidence regime, both 2021 openers** (2021-05-14 and 2021-05-15, 4 candidates each, 0 allocated) —
because 2021 has no prior season for S2 to reach into (test **D5**). That is the hard boundary of
this program's cold start: the first season of the universe cannot be rescued by any source in the
repository.

Obligations stranded by those two team-games are counted, not lost: the contract declares 44,851
obligations, the exposure artifact carries 44,843, and the validation receipt names the difference
as `"stranded": 8` (test **D6**).

## 7. Name resolution at the ingest boundary — quoted, not re-measured

`ROSTER_SOURCE_AUDIT_RECEIPT.json` is the only in-scope evidence about name→id resolution. Its
figures are **quoted here and were not recomputed by this node**, because the sources they describe
(`data/injury_history/`, `data/injury_capture/`) lie outside the read scope:

* transaction-wire acquisitions: 1,483 of 1,846 fully resolved (**80.34%**); releases **67.53%**;
* **`n_ambiguous_names_mapping_to_multiple_ids`: 0** — this is the receipt's alias evidence;
* team-abbreviation aliases handled: `POR→PDX`, `PHO→PHX`.

**REQUIREMENT N-1.** A one-in-five unresolved acquisition rate is a *reported* rate, not a benign
one. Any future Tier-A ingest that keys on names must carry its own resolution receipt with the
same three fields, and `n_ambiguous_names_mapping_to_multiple_ids > 0` must fail closed rather than
pick a winner.

## 8. What this contract does NOT establish

* It does not establish that no two `player_id`s denote the same person. With no name column in
  scope, an id split is **undetectable from these artifacts**. §1 removes the alias problem from
  *inside* the program; it does not prove the ingest that produced the ids was correct.
* It does not establish any accuracy, calibration or performance property of any fallback level.
  The strata are counted, never scored.
* It does not authorise `is_cold_start` as a model feature. Availability is not eligibility.
