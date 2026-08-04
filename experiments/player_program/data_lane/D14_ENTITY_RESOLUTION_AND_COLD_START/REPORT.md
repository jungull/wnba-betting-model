# D14 — Entity resolution and cold start

**Node:** `D14_ENTITY_RESOLUTION_AND_COLD_START` · lane `data` · type `implementation` ·
severity on failure `B` · role: data and cutoff-validity engineer.

## Epistemic status

> **DESIGN ARTIFACT + TESTS. Defines behaviour at the boundaries. Establishes no effect.**

Nothing in this node fits, tunes, scores, promotes or compares any arm. No forecast is compared to
any outcome. Nothing under `stage2b/SEALED_RESULTS/` was read or listed. The incumbent
`D_ewma_shrunk` was not touched.

## Outputs

| file | what it is |
|---|---|
| `IDENTITY_AND_COLD_START_CONTRACT.md` | the design artifact — declared behaviour at the identity and history boundaries |
| `TESTS.py` | 25 executable boundary tests, standalone runner, `main()` returns 1 on failure |
| `TEST_RESULTS.json` | machine-readable test output with the measured value behind every assertion |
| `FINDINGS.json` | structured findings, contradictions, escalations |
| `REPORT.md` | this file |

**Test status: 25 of 25 pass** (`cd data_lane/D14_ENTITY_RESOLUTION_AND_COLD_START && python
TESTS.py` -> exit 0). Twenty-two are `INVARIANT` (a failure would be a defect); three are
`PINNED_GAP` (they assert *current* behaviour that diverges from the spec or is an undeclared
hazard, so the divergence is visible in CI rather than rediscovered).

---

## 1. What I measured, and the command behind each number

All measurements run against the worktree
`C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program`, branch
`player-model-program` (verified with `git -C ... rev-parse --abbrev-ref HEAD`). Every figure below
is emitted by `TESTS.py` into `TEST_RESULTS.json` under the named test id, so `python TESTS.py`
reproduces the whole table; each row is the `measured` block of the test named in the last column.

The obligation grain matters: `projected_player_possessions_v1.parquet` has **120,262 rows** but
repeats each obligation once per evidence regime. All counts below are over the **44,843 distinct
`row_uid`** obligations (`pd.read_parquet(EXPOSURE).drop_duplicates("row_uid")`), covering 386
players, 1,495 games and 2,988 team-games.

### 1.1 Identity (tests A1-A5)

| measurement | value | test |
|---|---:|---|
| free-text player-name columns across the three registered player artifacts | **0** | A1 |
| `player_id` dtype / minimum, all artifacts | integer, 100720 | A1 |
| realised turnover-target players not in the candidate universe | **0** of 384 | A2 |
| realised possession players not in the candidate universe | **0** of 384 | A2 |
| duplicate `(player_id, game_id, team_id)` obligations | **0** | A5 |
| non-null `player1_id` values in `canonical_player_events/1` | 574,295 | A3 |
| distinct `player1_id` values | 1,064 | A3 |
| ... resolving to a universe player | **381** (532,265 rows, 92.68%) | A3 |
| ... that are **team ids** in the person field | **15 ids, 38,726 rows (6.74%)** | A3 |
| ... official-shaped (id < 100000) | **629 ids, 3,117 rows**, all `replay_or_administrative` | A3 |
| ... non-roster persons (id >= 100000, not in universe) | **39 ids, 187 rows** — 180 fouls (64 `Technical`), 7 ejections | A3 |
| team-actor rows by family | rebound 23,131 · timeout 12,227 · turnover 2,803 · violation 520 · foul 45 | A3 |
| team-actor turnovers vs `team_unattributed` in the reconciliation | **2,803 = 2,803** (of 42,081 total; 39,278 player-attributed) | A4 |

### 1.2 Team transitions (tests B1-B5)

| measurement | value | test |
|---|---:|---|
| realised multi-club player-seasons, registered vs recomputed from raw lineups | **82 = 82** (75 two-club, 7 three-club, of 1,039) | B1 |
| dual-claim obligations | **1,232** over **616** (player, game) pairs, 147 players, 153 games | B2 |
| clubs per claimed player-game | **exactly 2 on all 616** | B2 |
| rows where `candidate_claimed_by_multiple_teams` disagrees with the >1-club condition | **0** | B3 |
| Tier A player-seasons with >1 club | **91 of 1,058 (8.6%)**, max 3 clubs | B4 |
| Tier B player-seasons with >1 club | **678 of 1,496 (45.3%)**, max **7** clubs | B4 |
| team-transition debut obligations (prior appearance elsewhere, none for this club) | **75**, 60 players, 31 Tier A / 44 Tier B | B5 |
| ... of which carry `is_cold_start = False` | **75 of 75** | B5 |

### 1.3 Cold start (tests C1-C9)

| measurement | value | test |
|---|---:|---|
| obligations where `is_cold_start` disagrees with (`n_prior_appearances == 0`) | **0 of 44,843** | C1 |
| cold-start obligations | **8,300 (18.51%)** — 1,280 of 35,629 Tier A (3.6%), 7,020 of 9,214 Tier B (**76.2%**) | C1 |
| cold-start obligations served by the fitted conditional-minutes estimator | **0** | C2 |
| `is_fallback` / `fallback_level` disagreements, either target, either direction | **0** | C3 |
| nulls across 17 identity and cold-start declaration fields | **0** | C4 |
| `fallback_level == 4` rows | **4,989 = every season-2021 obligation, and no other row** | C5 |
| ... carrying `is_cold_start = False` | **13,944 of the regime-expanded rows**, median 12 prior appearances | C5 |
| level-4 disagreements between the two targets | **0** | C5 |
| ex-2021 cold-start rows keeping a **fitted** `p_active` | **4,501** (median 3 prior team games) | C6 |
| ex-2021 cold-start rows keeping a **fitted** `e_minutes_given_active` | **0** | C6 |
| ex-2021 obligations with exactly one prior appearance, by conditional-minutes level | **level 2: 1,697 · level 3: 201** | C7 |
| cold-start obligations with null or negative projected minutes | **0**, max 40.0 | C8 |
| obligations with null `projected_off_possessions` | **51**, all `team_game_status = minutes_only_no_pace` **and** `pace_source = unresolved_no_prior_games`, none with null minutes | C8 |
| audited obligations where `n_prior_appearances` differs from realised prior appearances | **474 of 28,107 (1.69%)**, direction -1 on **every one** | C9 |
| obligations flagged cold start that had in fact already played that season | **2** (2023, 2024; one player each) | C9 |

### 1.4 Tier and evidence (tests D1-D6)

| measurement | value | test |
|---|---:|---|
| Tier A assignment sources | `{S1, S3}` only | D1 |
| Tier B assignment sources | `{S_TX, S2}` only | D1 |
| occurrences of the reserved token `S4` in any `candidate_source` | **0** | D1 |
| `team_assignment_source` -> (`confidence`, `roster_evidence_regime`) | **1:1**, no exceptions: S1->verified/captured_asof · S3->verified/captured_asof · S_TX->probable/retrospective_effective_date · S2->weak/weak_prior_season | D2 |
| S3 admissions | **18 obligations, 18 distinct players**, 2026-07-30 to 2026-07-31; **none earlier** | D3 |
| team-games with zero Tier A candidates | **76** — 12/12/12/12/13/15 by season, exactly league size, all Regular Season | D4 |
| ... declared `unresolved_insufficient_candidates` with `n_candidates = 0`, `n_allocated = 0` | **76 of 76** | D4 |
| team-games still unresolved under the widest evidence regime | **2**, both 2021 openers (2021-05-14, 2021-05-15), 4 candidates each, 0 allocated | D5 |
| contract obligations vs obligations present in the exposure artifact | **44,851 vs 44,843**; the validation receipt declares `"stranded": 8` | D6 |

---

## 2. The consequential findings

### F1 — `player1_id` is a polymorphic actor id, and only one of its four non-player classes is handled

7.32% of actor-bearing event rows (42,030 of 574,295) do **not** denote a universe player. They
denote a team (38,726 rows), an official (3,117) or a non-roster person, almost certainly a coach
charged with a technical or ejected (187). `EVENT_LIMITATIONS.md` declares this hazard **for
rebounds only** — its gap 1 says both stores place a team id in the person field for a team
rebound, and proposes exactly the comparison I ran. My measurement extends it: **15,595 non-rebound
rows** (timeout, turnover, violation, foul) carry the same hazard, and the official and non-roster
person classes are declared nowhere I could find
(`grep -niE "official|referee|coach" event_contract_v1/*.md` returns nothing).

`player_turnover_targets/1` already resolves the team class exactly, so the pattern is available;
it simply has not been generalised. **A bare `player1_id` join in any future event-channel feature
would silently attribute team, official and coach events to players.**

### F2 — cold start is two orthogonal axes wearing one word

`fallback_level == 4` fires on **all 4,989 season-2021 obligations and on nothing else**,
identically for both targets, with 13,944 of the regime-expanded level-4 rows carrying
`is_cold_start = False` and a median of 12 prior appearances. That is not player novelty; it is the
first fold having no earlier season to fit on. `is_cold_start` is the player-history axis. The two
must never be pooled into one "cold-start stratum". See section 4 — this is escalation E2.

### F3 — the implemented `is_cold_start` is player-season; the spec says player-team-season

`PREDICTION_CONTRACT_V5_SPEC.md` section 3 defines `is_cold_start` as "no prior appearance for
**this team** this season". The bytes implement (`n_prior_appearances == 0`) at the player-season
grain, with zero exceptions over 44,843 rows. The consequence is measurable and one-directional:
**75 obligations that are a player's debut for a new club, after she has already played elsewhere
that season, are all flagged `is_cold_start = False`.** The archetypal cold start does not fire the
cold-start flag.

### F4 — `is_cold_start` is a statement about admitted evidence, not about the player

`n_prior_appearances` counts *admitted* prior appearances. Audited against realised box membership,
**474 of 28,107 obligations (1.69%) carry a value exactly one below reality, in that direction on
every single row** — the signature of an earlier appearance that was a candidate-universe miss.
The resulting false-cold-start rate is small but not zero: **2 obligations**. Any consumer reading
`is_cold_start` as "this player has never played" is wrong on those rows.

### F5 — the conditional-minutes ladder rule is undeclared in every readable artifact

Level 3 implies at most one prior appearance, but the converse fails badly: of 1,898 ex-2021
obligations with exactly one prior appearance, **1,697 sit at level 2 and 201 at level 3**. The
discriminating quantity is not among the emitted fields. The producing module (`cbs_v15`) is
outside this node's read scope, so **the ladder's numeric rule cannot be verified by any consumer
of the registered artifacts**. This is a documentation gap, not a defect in the values.

### F6 — the structural cold start is a team-game property, and it is handled correctly

Every club's season opener has zero Tier A candidates — 76 team-games, exactly league size each
season — and every one is declared `unresolved_insufficient_candidates` with zero candidates and
zero allocation. Nothing is manufactured. The weak tiers rescue 74; **the two that remain are both
2021 openers**, because the first season of the universe has no prior season for S2 to reach into.
That is the hard floor of this program's cold start and no source in the repository moves it. This
is a **positive** finding and the pattern the rest of the fallback surface should follow.

### F7 — multi-club candidacy must be reported per tier or it misdescribes transfers by 5x

Tier A gives 8.6% of player-seasons with more than one club, against a realised 7.9%. Tier B gives
45.3% and a **seven-club** maximum. A pooled figure would describe candidate inflation as player
movement.

---

## 3. Contradictions found

**X1 — document vs bytes, unresolved.** `PREDICTION_CONTRACT_V5_SPEC.md` section 3 defines
`is_cold_start` as team-scoped; the bytes implement it player-scoped. **75 obligations differ.**
I did not choose a winner.

**X2 — spec requirement not present in the artifact.** Spec section 3 states every Tier B row
carries `candidate_published_time`, `candidate_observed_time`, `candidate_evidence_time`,
`is_fallback` and `exclusion_reason` "without exception". **None of the five is present** in
`projected_player_possessions_v1.parquet`; the `keep` list in `build_projected_exposure.py`
(lines 218-222) does not select them. This is a propagation gap and not necessarily a contract
defect: the upstream contract parquet lives at `experiments/prediction_contract_v5/`, **outside
this node's read scope**, so I could not check whether it carries them.

**X3 — the spec's own history check is not computable from the artifact.** Spec section 9 requires
all three history fields on every emitted forecast. The exposure artifact carries
`n_prior_appearances` and `n_prior_team_games`; **`n_prior_candidate_obligations` is absent**, so
`n_prior_appearances <= n_prior_candidate_obligations` cannot be evaluated here. Same propagation
gap as X2.

**X4 — a repeated row count that is eight too high, reconciled but worth fixing.**
`build_projected_exposure.py` line 118, `PROJECTED_EXPOSURE_RECEIPT.json`,
`PROJECTED_EXPOSURE_VALIDATION.json` and `P3_EXPERIMENT_SUMMARY.md` all assert "**All 4,169**
B_transaction_sensitivity rows carry candidate_observed_time ...". The artifact carries **4,161**.
The same validation file records the contract count 4,169, `"stranded": 8` and
`"closes_to": 44851`, so the arithmetic is sound: 4,169 is the *contract* count and the prose
describes it as if it were the *artifact* count. Wording, not arithmetic — but it is the kind of
eight-row slippage that later gets cited as a row count.

**X5 — incomplete declaration.** `EVENT_LIMITATIONS.md` declares the team-id-in-person-field hazard
**only for rebounds**; it affects 15,595 further rows across timeout, turnover, violation and foul,
plus 629 official ids and 39 non-roster person ids that are declared nowhere. See F1.

I found **no** contradiction between any artifact and its receipt hashes, and no contradiction in
the tier, era or precedence rules — those hold exactly as specified (tests D1-D3).

---

## 4. Stop conditions and escalations

The node's stop condition is: *a finding would change the primary target, the K0 structure, the
inference structure, the candidate universe, the cutoff-valid feature set or the leakage status —
HALT and raise, do not resolve it inside the node.*

**I resolved none of the following. They are raised, not fixed.**

### E1 — the `is_cold_start` grain (X1/F3) meets the S6 stratum question

`V2_STOP_CONDITION.json` finding **S6** records that the incumbent's largest measurable defect is a
level error **on the cold-start strata** (bias 37.1% of MSE on `team_window_prior_season`, 42.5% on
`season_openers`, against 0.19% pooled), and that whether `K0_MATCHED` carries the tier structure
decides the wave. Any construction that stratifies by a cold-start indicator inherits the grain
question: under the spec's team-scoped definition 75 obligations move stratum; under the implemented
player-scoped one they do not. **The definition must be settled before any stratum is frozen into a
control.** This does not change which rows are in the universe — it changes which stratum they are
counted in.

### E2 — fallback level 4 is exactly collinear with the 2021 fold indicator (F2)

`V2_STOP_CONDITION.json` finding **S7** raises per-fold degeneracy for the **team pace ladder**: a
tier indicator identically zero in four of six chronological folds, "pooled healthy, fold
degenerate", landing on the authoritative control. **The same shape is present on the player ladder
and S7 does not name it.** `fallback_level == 4` is not merely degenerate in some folds — it is an
**exact indicator function of the 2021 fold**, 4,989 of 4,989, for both targets. Any design matrix
carrying both a fold effect and a player fallback-level dummy is rank-deficient by construction,
not by accident of sparsity.

I ran no rank or estimability check on any design matrix, and I did not touch `feature_gate.py`,
`comparison_gate.py` or `gate_invocation.py`. This is raised for the possession lane to adjudicate.

### E3 — the polymorphic actor id (F1/X5) is a prospective feature-set hazard

Every granular event channel the possession wave might build — turnovers by mechanism, rebounds,
fouls — reads `player1_id`. A naive join attributes 7.32% of actor rows to non-existent players,
and the largest affected family is **rebound (23,131 rows)**, which `EVENT_LIMITATIONS.md` already
flags as carrying `rebound_type = unresolved` on all 125,309 rows. I found **no evidence that any
existing artifact is corrupted by this**: `player_turnover_targets/1` handles the team class exactly
(2,803 = 2,803) and `player_possessions/2` derives from stints rather than from a `player1_id` join.
**This is a prospective hazard on the feature set, not a retrospective defect**, escalated so it is
closed before an event-channel arm is written rather than after.

### Not escalated

Nothing I measured changes the primary target
(`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`), the per-arm `K0_MATCHED` requirement, the
2,982 team-game / 1,491 game-cluster universe, or the leakage status of any column. I introduced no
same-game surrogate for realised duration, overtime or `game_minutes`. The postgame box membership
used in tests B5 and C9 audits the pregame universe's own counters only, which
`PREDICTION_CONTRACT_V5_SPEC.md` section 6 expressly permits and which creates no candidate.

---

## 5. What I could **not** establish, and why

1. **That no two `player_id`s denote the same person.** There is no free-text name column anywhere
   in the registered player artifacts (test A1) and every name-keyed source lies outside this
   node's read scope (`experiments/player_program/` only). The absence of names removes the alias
   problem from *inside* the program; it is **not** proof that the ingest which minted the ids was
   correct. An id split would be invisible here. **This is the single largest thing this node
   cannot verify. The acceptance criterion "transferred-player aliases resolve to one identity with
   evidence" is met in the narrower sense that a transfer is one id carrying two team_ids, verified
   against the raw lineups (test B1, 82 = 82) — not in the sense that the id minting was audited.**

2. **The name-to-id resolution rate.** `ROSTER_SOURCE_AUDIT_RECEIPT.json` reports 80.34% for
   acquisitions, 67.53% for releases and zero names mapping to multiple ids. I **quote** those
   figures; I did not recompute them, because `data/injury_history/` and `data/injury_capture/` are
   outside my read scope. They are cited as prior evidence, not as measurements of this node.

3. **The numeric rule separating fallback levels 2 and 3** (F5). 1,697 of 1,898 single-appearance
   obligations sit at level 2 and 201 at level 3; the discriminating field is not emitted and
   `cbs_v15` is out of scope.

4. **The author-intended meaning of level 2 versus level 3.** I measured what they partition; I did
   not read the code that assigns them, so I state the partition and not the intent.

5. **Whether the upstream contract carries the five Tier-B evidence-time columns and
   `n_prior_candidate_obligations`** (X2, X3). `experiments/prediction_contract_v5/` is outside the
   read scope. The exposure builder's producer check only covers columns in its own `keep` list,
   which excludes them, so its passing tells us nothing either way.

6. **What the 8 stranded obligations are.** They are absent from the artifact by construction, so
   their tier, players and cold-start status cannot be read from it. The validation receipt declares
   the count and the two unresolved team-games; it does not enumerate the rows.

7. **Any performance, accuracy or calibration property of any fallback stratum.** Prohibited by the
   no-performance-peeking rule and out of scope for this node. The strata are counted only.

8. **Whether the 39 non-roster person ids are coaches.** The evidence is strongly consistent — 180
   fouls of which 64 are explicitly `Technical`, 7 ejections, ids in the person range, no other
   event family — but no roster or staff table is in scope to confirm it. Recorded as "non-roster
   person", not as "coach".

---

## 6. Reproduction

```
cd experiments/player_program/data_lane/D14_ENTITY_RESOLUTION_AND_COLD_START
python TESTS.py            # 25/25 pass, exit 0, writes TEST_RESULTS.json
python -c "import json;json.load(open('FINDINGS.json'))"
```

`TESTS.py` reads only under `experiments/player_program/`. It writes only `TEST_RESULTS.json` in
this directory. It runs no git command.
