# `prediction_contract_v5` — a candidacy universe that admits players who arrive after tip-off of the season

**Status:** SPECIFIED and registered. **Not implemented.** No v5 artifact exists.
**Registered in:** `experiments/player_program/registry.jsonl` (the player program's own registry;
the shared `experiments/registry.jsonl` is untouched).
**Supersedes:** nothing. `prediction_contract_v4` is **not edited, not amended and not
regenerated.** v5 is a new contract version alongside it.
**Evidence label:** specification only. Nothing is fitted, predicted or scored anywhere in this
document. "Coverage" means obligation completeness.

---

## 1. The defect, measured

`prediction_contract_v4`'s membership rule is
`prior_admitted_team_game_box_membership_including_dnp/1`:

> a candidate for `(team, game)` is a player who appears as a row in that team's box score for one
> of the latest **five prior same-season** team games whose availability bound is strictly earlier
> than the row's forecast cutoff.

Candidacy is therefore established **only** by having already been in that club's box score, this
season. Two classes of real player-game are consequently unforecastable. Measured against
`master_player.parquet` by `audit_candidacy_gap.py` → `CANDIDACY_GAP_RECEIPT.json`:

| | rows | distinct players | distinct games |
|---|---|---|---|
| played player-team-games (`minutes > 0`) | 28,322 | | |
| **not an obligation** | **977 (3.45%)** | 356 | 233 |

Decomposed by cause — and the decomposition is the point, because the two classes need different
remedies:

| cause | rows | share | why |
|---|---|---|---|
| **`season_opener`** | **749** | 77% | "prior **same-season** game" does not exist for team-game 0, so **every team's first game of every season yields zero candidates and zero obligations** |
| **`mid_season_arrival`** (team-game index ≥ 5) | **176** | 18% | signings, hardship contracts, waiver claims and trades: no box row for the *new* club inside the window |
| **`early_season_partial_window`** (index 1–4) | 52 | 5% | window not yet full |

Per season the rate is stable at 2.9–4.6%, so this is structural, not an era artifact.

**The 51 rows reported in the Phase 0 audit were a subset of this**, visible only where the
registered minutes universe overlapped the contract. The true figure is 977.

### The old club keeps the obligation the new club never gets

A traded player remains in the old club's five-game window, so v4 owes a forecast for a club she
has left while owing none for the club she plays for. This is the same mechanism that produces the
14 dual-team head-to-head obligations `cbs_real_frames/3` handles, seen from the other side.

## 2. What evidence actually exists — and what does not

Established by inspection of the repository, not assumed:

| source | what it proves | as-of timestamp | span |
|---|---|---|---|
| `data/masters/master_player.parquet` | box membership, including DNP rows | game availability bound | 2021 → 2026, complete |
| `data/w1_truth/roster_asof.csv` | **derived from box scores** — `first_game_date`, `last_game_date`, `n_games`. A tenure *summary*, not a roster feed | artifact-level only | 2021 → 2026 |
| `data/injury_capture/injury_log.csv` | official pregame availability report: team, player, status, reason — **a genuine pregame roster signal** | `capture_utc`, per row | **2026-07-30 → 2026-08-01 only** |
| `data/news_capture/news_items.csv` | unstructured text, players mentioned | `published_utc` | 2026 forward |
| **a transaction log** | signings, waivers, trades with timestamps | — | **DOES NOT EXIST** |

`MINUTES_MODEL_SPEC` §10 already carries transaction-log capture as an open ledger item. It was
never built.

**Consequence, stated plainly:** historically, a signing or trade becomes observable in this
repository only when the player first appears in a box score — which is the very game that needs
forecasting. **Roster membership cannot be reconstructed from box scores alone.**

### The one remedy that uses provable evidence, and how far it goes

A player's box appearance in a **previous season for the same franchise** is available months
before an opening-night cutoff. Admitting it invents nothing and is cutoff-safe by construction.
Measured:

| | recovered | of | rate |
|---|---|---|---|
| season openers, all seasons | 324 | 749 | 43.3% |
| season openers, excluding 2021 | 324 | 633 | **51.2%** |
| mid-season arrivals | 22 | 176 | 12.5% |

2021 recovers nothing because it is the earliest season in the data. The residue — 425 openers and
154 mid-season arrivals — are genuine newcomers: rookies, free agents arriving from another
franchise, players returning from overseas. **No box score anywhere contains them before the game
they first play.**

v5 therefore closes roughly half the opening-night gap with provable evidence and **declares the
rest an audited exclusion rather than manufacturing it.**

## 3. Design

### 3.1 Candidacy is a union of evidence sources, each with its own provable as-of bound

A player is a candidate for `(team, game)` if **any** admitted source names her for that team,
where a source is admitted only if its as-of bound is **strictly earlier** than the row's
`forecast_cutoff`. Every obligation records **which** sources named it.

| id | source | rule | availability |
|---|---|---|---|
| **S1** | in-season box membership | v4's rule, unchanged: box row in one of the latest 5 admitted prior same-season team games | all seasons |
| **S2** | prior-season franchise membership | box row for the same `team_id` in **any** strictly-earlier season, admitted only for team-game index `< S2_HORIZON` | 2022+ |
| **S3** | captured pregame availability report | the player is listed for that team on an official report whose `capture_utc` is strictly earlier than the cutoff | **2026-07-30 onward** |
| **S4** | transaction feed | reserved. **Declared unavailable.** No implementation may silently substitute another source for it | never |

`S2_HORIZON` is a registered constant, default **5** (team-game indices 0–4), so prior-season
evidence establishes candidacy only while in-season evidence is thin and never overrides it later.
S1 remains the sole source from index `S2_HORIZON` onward.

**S2 over-includes by design.** Offseason turnover means many prior-season players are gone. That
is acceptable and is *not* a defect: candidacy is a superset over which `p_active` is defined, and
`P(active)` is precisely the model that assigns low probability to a player who is no longer
there. Over-inclusion costs obligations; under-inclusion costs *forecastability*, which cannot be
recovered downstream. The asymmetry is the reason the union is a union.

**Every source is a hard-evidence source.** None infers membership from absence, and none uses a
future observation. S4 is present in the schema and explicitly unavailable so that a later
implementation cannot quietly fill the slot with something weaker.

### 3.2 Eras are declared, not smoothed over

S3 exists only from 2026-07-30. A contract that reported one uniform coverage figure across
2021–2026 would misrepresent that. v5 declares:

| era | span | sources | status |
|---|---|---|---|
| `box_only` | 2021 → 2026-07-29 | S1, S2 | historical; mid-season arrivals are **excluded**, audited |
| `report_assisted` | 2026-07-30 → | S1, S2, S3 | current; mid-season arrivals **admissible** where a report names them before cutoff |

Coverage is reported **per era**. A model fitted across the boundary must record that its training
window spans two candidacy regimes; that is a modelling constraint v5 surfaces rather than hides.

### 3.3 Transactions, teams and timestamps

* **How a transaction is timestamped.** Only by the `capture_utc` of the artifact that recorded
  it. There is no other clock. An S3 row's bound is its own capture time, never the report's
  nominal date, because a report can be published after its nominal date.
* **How a traded player changes teams.** She becomes a candidate for the new club when an admitted
  source names her for it — S3 in the report era, S1 once she has a box row. She *remains* a
  candidate for the old club while she is still inside its S1 window, and both obligations are
  owed. This is v4's dual-obligation behaviour, retained deliberately: at cutoff the contract
  cannot know she has gone, and `cbs_obligation_key.row_uid` already names both rows distinctly.
  The old-club row carries `master_row_present = False` — absence of an event, not missing data.
* **Same-day and uncertain transactions.** A source whose as-of bound is **not strictly earlier**
  than the cutoff is **not admitted**. Equality is a violation, not a pass — v4's existing rule,
  retained. A transaction that cannot be placed strictly before the cutoff does not create
  candidacy, and the resulting played-but-unforecast row is audited under §3.5.
* **When historical roster timestamps are unavailable** — which is the normal case before
  2026-07-30 — v5 does **not** invent one. The obligation is not created, and the row appears in
  the exclusion audit.

### 3.4 Cold start and fallback

Candidacy and history are separate questions and v5 keeps them separate.

An S2- or S3-established candidate typically has **no in-season history at all**. She is a valid
obligation with an empty history, which is exactly the case the fallback ladder exists for. v5
requires each obligation to carry its establishing sources plus the three history counts of §4, so
a consumer can distinguish:

| state | meaning |
|---|---|
| `established_by: [S1]`, history present | ordinary rotation player |
| `established_by: [S2]`, no history | returning player, opening night — **cold** |
| `established_by: [S3]`, no history | newly reported arrival — **cold**, report era only |
| `established_by: [S1, S2]` | corroborated |

No fallback *level* is defined here. The ladder belongs to the arm, not the contract; the contract
supplies the counts the ladder reads.

### 3.5 The exclusion audit is mandatory and is part of the build

Every v5 build **must** emit `candidacy_exclusion_audit.json` enumerating every
`(game_id, team_id, player_id)` with `minutes > 0` and no obligation, each carrying:

* `cause` ∈ {`season_opener`, `early_season_partial_window`, `mid_season_arrival`,
  `game_absent_from_master_index`}
* `era`
* which sources were checked and why each declined
* `recoverable_by_prior_season_membership`

A build whose exclusion audit is absent or unreadable **fails**. The count is permitted to be
non-zero — it will be — but it is never permitted to be *unknown*. This is the specific discipline
whose absence let 977 rows go unnoticed through five contract versions.

**The 51 rows from the Phase 0 audit and the 977 measured here are preserved as evidence of the v4
defect.** They are not added to v4. `CANDIDACY_GAP_RECEIPT.json` is their record.

### 3.6 What v5 deliberately does not change

Carried from v4 unchanged, so the diff is the candidacy universe and nothing else: the canonical
`row_uid` = `cbs_obligation_key.row_uid(player_id, game_id, team_id)`; the cutoff policy and its
strict-inequality admission; the `+36h` outcome-availability policy; box-membership-including-DNP
semantics for S1; the four registered player targets; and the `prediction_required` /
`outcome_scoreable` split.

## 4. `n_prior_games` is retired and replaced by three named fields

**Defect P-D3.** `cbs_player_runner_v14` emits `n_prior_games` meaning
`n_prior_candidate_games` for `p_active` on fitted folds but `n_prior_appearances` for all four
targets on the degenerate 2021 fold. One column, three meanings, silently varying by fold and by
target. Any per-history-bucket report that pools 2021 with later seasons buckets on the wrong
quantity.

v5 forbids the overload. Three fields, each defined once and never conditioned on fold or target:

| field | definition |
|---|---|
| `n_prior_candidate_obligations` | obligations in the same `(player_id, season)` whose `forecast_cutoff` is **strictly earlier** than this row's. Counts obligations, not distinct games: two obligations owed for one earlier contest contribute two. This is `cbs_player_history/14`'s corrected count, renamed |
| `n_prior_appearances` | admitted prior rows in the same `(player_id, season)` with `appeared = True` |
| `n_prior_team_games` | admitted prior games of this row's `team_id` in this season, regardless of the player |

Every emitted forecast carries all three. A target reads whichever it needs — `p_active` reads
candidate obligations, the conditional targets read appearances — and **which one it read is
recorded in the prediction row**, so the semantics of a history bucket are readable from the
artifact instead of inferred from the runner's source.

`n_prior_games` is not emitted by v5 under any circumstances. A consumer requesting it gets an
error, not a guess.

## 5. Validation the build must pass

Ordered; each fails closed.

1. **Key identity** — `row_uid` unique on every frame and re-derivable from
   `(player_id, game_id, team_id)`; `obligation_key_id` declared.
2. **Cutoff safety** — every admitted source's as-of bound strictly earlier than the row's
   `forecast_cutoff`; equality refused.
3. **Source attribution** — every obligation names ≥1 establishing source; every named source was
   admitted; S4 never appears.
4. **Era declaration** — every row carries its era; S3 never establishes candidacy before
   2026-07-30.
5. **Superset property** — every v4 obligation is a v5 obligation. v5 may only *add*. A missing v4
   row is a hard failure, checked by key-set containment and reported as
   `row_diff_vs_v4.json`.
6. **History fields** — all three present, non-negative; `n_prior_appearances ≤
   n_prior_candidate_obligations` on every row; `n_prior_games` absent.
7. **Exclusion audit** — present, readable, enumerated, with a cause for every row.
8. **Coverage reconciliation** — per era and per season: obligations, played-and-obligated,
   played-and-excluded, and the exclusion rate. Reported, never asserted to be zero.

## 6. Expected effect, stated before the build so it can be checked against

Predictions this specification commits to, from the §1 and §2 measurements:

* v5 obligations ⊃ v4 obligations, strictly. Growth comes mostly from opening night.
* Roughly **324** currently-excluded opener rows become obligations via S2 (≈51% of openers
  outside 2021); the remaining ≈425 stay excluded and audited.
* Mid-season arrivals stay excluded in the `box_only` era. In the `report_assisted` era they
  become admissible, and the exclusion audit is what will show whether S3 actually catches them.
* 2021 openers remain wholly unrecoverable. This is a property of the data's left edge and no
  contract version can fix it.
* Total obligations rise by roughly the number of new candidates per opener × games, which is
  materially larger than 324, because S2 admits *candidates* and only some candidates play. The
  build must report the realised figure; nothing here should be taken as a target.

**A v5 build that reports a zero exclusion count has a bug**, not a triumph.

## 7. What is NOT authorised by this specification

Implementation, generation, any regeneration of v4, any change to the shared
`experiments/registry.jsonl`, any change to team-thread artifacts, and any scoring. v5 is a
specification and a registration. It is frozen at registration; corrections go to an erratum, per
`project_docs/SPEC_ERRATA.md`.
