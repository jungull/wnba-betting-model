# D10_FIELD_AVAILABILITY_LEDGER — field-level cutoff-validity coverage across every candidate source

**Epistemic status (verbatim, as issued):**

> VERIFIED_READ_ONLY_DERIVATION. An availability ledger. Availability is not eligibility and
> eligibility is not admission.

**Lane:** data · **Type:** audit · **Node severity on failure:** B
**Outputs:** `FINDINGS.json` (machine-readable ledger, 52 fields), `build_ledger.py` (producer),
`TESTS.py` (structural checks), this report.

Nothing outside `experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/` was written.
No git command was run. Nothing under `stage2b/SEALED_RESULTS/` was read. Nothing was fitted,
predicted or scored, and no comparative historical performance of any challenger was inspected.

---

## 1. The one-sentence result

Of 52 candidate fields across the twelve families this node was asked to cover, **five are
cutoff-valid, thirty-seven are CUTOFF_UNPROVEN, three are CUTOFF_INVALID and seven do not exist** —
and of the five cutoff-valid fields, **four are confined to a three-day window in 2026 and one
begins in the 2025 season**. Across 2021–2024 — 1,932 of the universe's 2,982 team-game rows —
**not one field in this ledger clears its own declared pregame cutoff.**

That is not a coverage problem. Availability is near-total: most fields resolve on 97–100% of rows.
It is an *eligibility* problem, and the two must never be reported as one number.

---

## 2. What the numbers are measured against

**Row universe.** `team_possession_universe/1` as returned by `possession_features.load_universe()`:
**2,982 team-game rows over 1,491 game clusters**, row-universe digest
`raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371`. Both counts are reported
everywhere; a team-game number is never presented as a game number.

**Folds.** `possession_features.chronological_folds()` — expanding-window, one fold per season with
at least one strictly earlier season. Games are never split across a fold boundary; `TESTS.py`
enforces this by requiring every train and test row count to be even.

| fold | cutoff date | train rows | test rows |
|---|---|---:|---:|
| `train_lt_2022` | 2022-05-06 | 410 | 478 |
| `train_lt_2023` | 2023-05-19 | 888 | 520 |
| `train_lt_2024` | 2024-05-14 | 1,408 | 524 |
| `train_lt_2025` | 2025-05-16 | 1,932 | 620 |
| `train_lt_2026` | 2026-05-08 | 2,552 | 430 |

**The declared pregame cutoff is not invented here.** It is read per game from
`experiments/prediction_contract_v4/game.parquet::forecast_cutoff`, which the repository already
fixes as either `exact_tip_T-90m` (scheduled tip minus 90 minutes, admitted only where an
observation satisfied `observed_at < tip - 90 min`) or `date_only_prior_day_cutoff` (18:00 UTC on
the day *before* the game). All 1,491 universe games join to a cutoff — measured, not assumed. Over
the universe's team-game rows: **2,168 date-only, 814 exact-tip**.

**The rule applied.** A field is `CUTOFF_VALID` for a row only if a *per-row source observation
timestamp* exists and is `<=` that row's own `forecast_cutoff`. No timestamp means
`CUTOFF_UNPROVEN`. Structural plausibility — "a schedule is obviously known in advance", "a city's
elevation does not change" — is an argument, and this ledger does not accept arguments in place of
evidence. Each `CUTOFF_UNPROVEN` field additionally carries a `structural_class` explaining *why*
the proof is absent; that is an explanation, never a downgrade of the verdict.

---

## 3. Verdict tally

| family | fields | CUTOFF_VALID | CUTOFF_UNPROVEN | CUTOFF_INVALID | ABSENT |
|---|---:|---:|---:|---:|---:|
| schedules | 8 | 0 | 7 | 0 | 1 |
| rest | 4 | 0 | 4 | 0 | 0 |
| venues | 3 | 0 | 3 | 0 | 0 |
| travel | 3 | 0 | 3 | 0 | 0 |
| elevation | 2 | 0 | 2 | 0 | 0 |
| time zones | 3 | 0 | 3 | 0 | 0 |
| tip times | 5 | 1 | 3 | 1 | 0 |
| injuries | 5 | 3 | 2 | 0 | 0 |
| transactions | 5 | 0 | 3 | 0 | 2 |
| roster continuity | 5 | 1 | 2 | 2 | 0 |
| coaching | 4 | 0 | 0 | 0 | 4 |
| opponent history | 5 | 0 | 5 | 0 | 0 |
| **total** | **52** | **5** | **37** | **3** | **7** |

Produced by `python experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py`,
which prints `fields: 52  verdicts: {'CUTOFF_UNPROVEN': 37, 'ABSENT': 7, 'CUTOFF_VALID': 5,
'CUTOFF_INVALID': 3}`. Per-family tallies recomputed from `FINDINGS.json` by crosstabbing `family`
against `verdict`.

---

## 4. What I measured, per family, and how

Every figure below comes from `build_ledger.py`. Re-run it and read `FINDINGS.json`: every field
record carries `coverage.overall`, `coverage.by_season`, `coverage.by_season_type` and
`coverage.by_fold` with separate `train` and `test` cells, and both a `covered` and a
`cutoff_valid` count at every level. Nothing is pooled.

### 4.1 Schedules — 100% available, 0% provable

`sched.game_id`, `sched.game_date`, `sched.season`, `sched.season_type`, `sched.is_home`,
`sched.opp_team_id`, `sched.team_abbreviation` each resolve on **2,982 / 2,982 rows (100%) in every
season and on both sides of every fold** — and each is **CUTOFF_UNPROVEN**.

The reason is a single measured fact. `data/masters/master_team.parquet` carries an `observed_time`
column with **10 distinct values across 2,990 rows**, all 2026 bulk-scrape moments. Measured against
each row's own cutoff:

- universe rows whose `observed_time` is strictly **after their own `forecast_cutoff`: 2,982 of 2,982**;
- universe rows whose `observed_time` is strictly **after the game itself: 2,982 of 2,982**.

The schedule is a pregame fact. The *only artifact in this repository that carries it* is a
completed-game team box score observed months to years later. No pre-cutoff observation of the WNBA
schedule exists anywhere that was searched.

`sched.neutral_site_flag` is **ABSENT**. `grep -rn -i 'neutral'` over the worktree returns only
play-by-play `NEUTRALDESCRIPTION` text and unrelated "neutralized" feature language. No column, file
or code marks any game as played at a neutral site. **Every venue, travel, elevation and time-zone
field in this ledger therefore inherits an unverified assumption that the venue is the home team's
own arena.** That assumption is load-bearing for four families and is nowhere tested.

### 4.2 Rest — derived from the schedule, therefore capped by it

| field | coverage | verdict |
|---|---|---|
| `rest.days_since_prev_game` | 2,906 / 2,982 = **97.45%** | CUTOFF_UNPROVEN |
| `rest.is_back_to_back` | 2,906 / 2,982 = **97.45%** (True on **89** rows) | CUTOFF_UNPROVEN |
| `rest.games_in_prev_7_days` | 2,982 / 2,982 = **100%** | CUTOFF_UNPROVEN |
| `rest.is_season_opener` | 2,982 / 2,982 = **100%** (True on **76** rows) | CUTOFF_UNPROVEN |

The 76 uncovered rows are each team's first game of a season: **censoring, not missingness**, and
labelled as such in the ledger. By fold, `rest.days_since_prev_game` test coverage runs 0.975 /
0.977 / 0.977 / 0.979 / 0.965 — flat, with the 2026 test fold slightly lower because the 2026 season
is partial. A derivation adds no observation: these fields carry `master_team`'s provenance and
cannot be better than it.

### 4.3 Venues, travel, elevation, time zones — one 16-row table with no timestamp at all

All eleven fields resolve from `data/reference/team_cities.csv` (16 rows, sha256 `10a544fd...`) plus
the schedule. Static attributes (`venue.arena_name`, `venue.city`, `travel.venue_lat`,
`travel.venue_lon`, `elevation.venue_elevation_ft`, `timezone.venue_iana_timezone`,
`timezone.venue_utc_offset_hours`) are **100% covered in every season and every fold**.
Previous-venue derivations (`travel.km_from_prev_venue`, `elevation.delta_from_prev_venue_ft`,
`timezone.shift_from_prev_venue_hours`) are **97.45%** covered — the same 76 season-opener rows.

All eleven are **CUTOFF_UNPROVEN**, for one reason: `team_cities.csv` has **no capture timestamp of
any kind** — no column, no sidecar manifest, no fetch record. `collect_bios.py` states in a comment
that lat/lon are city-level and `elevation_ft` approximate.

Measured properties worth having on record:

- `travel.km_from_prev_venue`: median non-null **863.6 km**, max **4,266.5 km**. It is a
  *schedule-order surrogate* for travel, not an itinerary — **no flight, departure, arrival or
  lodging record exists anywhere in the repository**.
- Elevation is a three-arena contrast, not a continuum. The only venues above 1,000 ft in
  `team_cities.csv` are LVA (2,030), PHO/PHX (1,090) and ATL (1,010); the next is MIN at 830.
- `timezone.shift_from_prev_venue_hours` is non-zero on **1,103 of 2,982 rows**, computed by
  resolving the IANA zone on the row's own `game_date` through `zoneinfo`, so DST is handled rather
  than assumed.

### 4.4 Tip times — the one place a real cutoff screen exists, and the one place it was thrown away

Two artifacts describe the same quantity and disagree about whether it is knowable.

**`data/reference/tip_times.csv`** covers **1,219 of 1,491 universe games**; at team-game level
`tip.tip_utc__tip_times_csv`, `tip.tip_hour_local` and `tip.tip_dow_local` are **2,438 / 2,982 =
81.76%** covered. All three are **CUTOFF_UNPROVEN**. `collect_bios.py::phase_tips` takes the
**latest** odds snapshot per game ("the final scheduled tip that source saw") and **does not retain
`odds_snapshot_timestamp` in the output**. The underlying odds tables carry a per-snapshot
timestamp; this file discards it. A latest-snapshot value cannot be shown to predate the cutoff —
the latest snapshot may postdate the tip. **The unprovenness is a property of the derivation, not of
the underlying feed**, which makes it repairable.

**`experiments/prediction_contract_v4/game.parquet`** carries the screened version.
`prediction_contract_v2::resolve_tip_times` admits an observation only when
`observed_at < tip - 90 min`, takes the latest qualifying observation, and fails closed to the
date-only policy otherwise. Re-measured here: of the rows carrying a `scheduled_tip_time`, **814 of
814 have `tip_time_observed_at <= their own forecast_cutoff`**.
`tip.scheduled_tip_time__contract_v4_screened` is therefore **CUTOFF_VALID on 814 of 2,982 rows
(27.30%)** — the only field in this entire ledger that clears the cutoff test on any row before
2026.

**By fold, this field is the clearest demonstration of why pooling is forbidden:**

| fold | train covered | test covered | test cutoff-valid rate |
|---|---|---|---|
| `train_lt_2022` | 0 / 410 = 0.000 | 0 / 478 = 0.000 | 0.000 |
| `train_lt_2023` | 0 / 888 = 0.000 | 0 / 520 = 0.000 | 0.000 |
| `train_lt_2024` | 0 / 1,408 = 0.000 | 0 / 524 = 0.000 | 0.000 |
| `train_lt_2025` | 0 / 1,932 = 0.000 | 394 / 620 = 0.635 | **0.635** |
| `train_lt_2026` | 394 / 2,552 = 0.154 | 420 / 430 = 0.977 | **0.977** |

A pooled 27.3% would read as "usable on a quarter of the data". The fold view says something
different and decision-relevant: the field is **structurally absent from four of five training
sets** and appears only in the last two test seasons.

The unscreened `tip_times.csv` has the same shape in milder form: `train_lt_2022` has **zero** tip
coverage on its training side (2021 has no tip data at all) against 75.3% on its test side. By
season type it is 83.25% on Regular Season rows and **62.26% on Playoffs rows** — thinner exactly
where the games are scarcest.

`tip.tip_hour_et__pbp_wallclock` is **CUTOFF_INVALID**. `features/common.py` derives it from the
play-by-play wall clock; the play-by-play of a game is produced *by* that game. A tip hour read off
the target game's own event stream is a postgame reconstruction of the schedule, not a pregame
observation of it. (The legacy store carries `WCTIMESTRING` directly; the modern CDN store carries
no wall-clock column and would need `(7:03 PM EST)` parsed out of the period-start description.)
Coverage is reported as 0 because this node **did not derive it** — building a cutoff-invalid
surrogate in order to quantify it would be constructing the thing the verdict rejects.

### 4.5 Injuries — the only genuinely point-in-time feed, and it barely intersects the universe

`data/injury_capture/injury_log.csv` (551 rows, sha256 `f3ad40b9...`) is the only availability source
in the repository with a real per-row observation timestamp: `capture_utc`, spanning **2026-07-30
15:49:50Z to 2026-08-01 15:00:05Z**. Revisions are preserved as separate timestamped rows rather
than overwritten. `injury.status`, `injury.reason` and `injury.report_date` are therefore
**CUTOFF_VALID** — within a span that intersects the possession universe on **12 of 2,982 team-game
rows (0.40%), across 6 of 1,491 game clusters**, all in the 2026 test fold. `game_date` is null on
**38 of 551 rows** (all `source=espn`); those are unattributable to a specific game and are excluded
from the join. All 15 team labels mapped cleanly (0 unmapped).

**Of those 12 overlapping rows, only 2 clear their own declared cutoff.** This is the sharpest
operational finding in the node and it is *not* a capture failure:

> Official pregame availability reports are published **on game day**. The
> `date_only_prior_day_cutoff` policy sits at **18:00 UTC the day before**. On any game that did not
> earn an `exact_tip_T-90m` cutoff, the report does not yet exist at the cutoff, and the feed is
> unusable no matter how well it was captured. The 2 rows that clear are the single universe game
> carrying an exact tip cutoff (`1022600212`, cutoff 2026-07-31T00:40Z, earliest qualifying capture
> 2026-07-30T15:49:50Z).

This is a **policy interaction**, and it will recur for every future game that lacks a qualifying
tip observation. Capturing more injury data does not fix it.

The retrospective side: `injury.missed_game_injury_wire` covers **1,262 / 2,982 = 42.32%** and
`injury.missed_game_other_wire` **1,758 / 2,982 = 58.95%**, both **CUTOFF_UNPROVEN**, both
strikingly flat across folds (injury-wire test coverage 0.358 / 0.412 / 0.408 / 0.474 / 0.442).
Their `date` is a real per-row *effective* date; their *observation* time is a single retrospective
moment.

### 4.6 Transactions — 100% availability, 0% eligibility, in the same row

`transactions.acquisition_effective_date` (1,991 dated rows; median 22 prior in-season records per
covered row, max 51) and `transactions.release_effective_date` are **covered on 2,982 / 2,982 rows
(100%) in every season and every fold** and are **CUTOFF_UNPROVEN on every one of them**. If a
single line in this report has to carry the availability/eligibility distinction, it is that one.

`transactions.observation_time` is **CUTOFF_UNPROVEN** with a second-order problem worth naming: the
archive's observation time is a single moment (2026-07-30) that **is not in the artifact** — it is
recoverable only from git history (commit `98271bb`) as recorded by
`ROSTER_SOURCE_AUDIT_RECEIPT.json`. A field whose observation time lives outside the bytes it
describes cannot be checked by any producer or gate that reads only the bytes. Measured: **2,972 of
2,982 universe rows (99.66%) have a `forecast_cutoff` strictly earlier than that observation
moment**, i.e. for 99.66% of the universe this archive is provably retrospective.

`transactions.publication_time` and `transactions.official_league_wire` are **ABSENT**. No column in
any transaction artifact records when a move was published; the official wnba.com transaction log is
not captured anywhere under `data/` and nothing in the repository fetches it. Re-confirmed here
against the worktree, consistent with `ROSTER_SOURCE_AUDIT_RECEIPT.json`.

### 4.7 Roster continuity

- `roster.prior_in_season_box_membership` — **2,914 / 2,982 = 97.72%**, median 14 prior distinct
  players. **CUTOFF_UNPROVEN.** The v4/v5 Tier-A rule S1 is *logically* cutoff-safe: a prior game's
  box exists before this game's cutoff. But the only artifact carrying it, `master_player`, has
  `observed_time` values that are all 2026 bulk scrapes, so **the file cannot prove the box was
  observed before the cutoff even though the underlying event preceded it**. The ledger records the
  gap rather than accepting the logic in place of the timestamp.
- `roster.continuity_vs_prev_game` — **2,914 / 2,982 = 97.72%**, undefined on 68 season openers.
  **CUTOFF_UNPROVEN**, and flagged in its own evidence as a *postgame description*: it uses this
  game's own box to determine who dressed. A pregame version would have to be built from a projected
  rotation, which exists (`projected_player_possessions/1`) and is a different artifact.
- `roster.starter_flag` — **CUTOFF_INVALID**. Who actually started the game being predicted. Listed
  so it is on the record as rejected rather than merely unmentioned.
- `roster.roster_asof_tenure` (`data/w1_truth/roster_asof.csv`, 762 rows) — **CUTOFF_INVALID**. Its
  name invites the opposite conclusion. `first_game_date` is the date a player first *appeared*,
  which is precisely the information that arrives too late to establish affiliation before that
  game.
- `roster.captured_availability_affiliation` — **CUTOFF_VALID**, same 12-row / 2-valid-row footprint
  as 4.5. It is the only source in the repository that can affiliate a player carrying no prior box
  row, and it exists for three days.

### 4.8 Coaching — nothing exists

All four fields (`head_coach_identity`, `coach_tenure_games`, `coach_change_flag`,
`rotation_policy`) are **ABSENT**, coverage 0 in every season and every fold.

Searched: `grep -rn -i coach` over `features/`, `data/` and `experiments/player_program/` returns
only (a) free-text "Coach's Decision" reason strings inside `injury_log.csv`, which name no coach,
and (b) two orchestration prompt filenames. `find . -iname '*coach*'` returns two markdown files and
no data file. There is no head-coach column, no coach identity table, no tenure record and no
coaching-change log anywhere in the worktree. `PLAYER_MODEL_CAPABILITY_MATRIX.md` independently
records the coaching track as `not started` with "No code, artifact or registration", which this
node confirms against the bytes.

**This is a negative result and it is preserved as one.** Any hypothesis in the Stage 2A packets
that rests on coaching or rotation-strategy identity has no data behind it in this repository.

### 4.9 Opponent history

| field | coverage | verdict |
|---|---|---|
| `opponent.n_prior_meetings_this_season` | 2,982 / 2,982 = **100%** (zero on 890 rows — first meeting) | CUTOFF_UNPROVEN |
| `opponent.days_since_last_meeting` | 2,092 / 2,982 = **70.15%** | CUTOFF_UNPROVEN |
| `opponent.prior_game_evidence_depth` | 2,982 / 2,982 = **100%** | CUTOFF_UNPROVEN |
| `opponent.opp_pace_estimate` | 2,982 / 2,982 = **100%** | CUTOFF_UNPROVEN |
| `opponent.prior_box_aggregates` | 2,092 / 2,982 = **70.15%** | CUTOFF_UNPROVEN |

`opponent.days_since_last_meeting` test coverage by fold is 0.724 / 0.746 / 0.748 / 0.748 /
**0.521** — the 2026 test fold is materially thinner because the 2026 season is only partially
played, which a pooled 70.15% would hide entirely.

The last two rows of that table are the ledger's hardest case and are discussed in section 7.

---

## 5. Adjacent captured feeds, recorded so their absence from the field list is deliberate

- `data/news_capture/news_items.csv` — **2,265 rows**, `capture_utc` **and** `published_utc` per row,
  published span 2026-05-20T12:03:06Z to 2026-08-01T15:30:14Z. Genuinely point-in-time within its
  span, but the content is prose; it is not a field source without a registered extraction layer.
- `data/ref_assignments/assignments_log.csv` — **69 rows**, per-row `capture_utc`, span
  20260730T170806Z to 20260801T140002Z. Officiating crew per game. Not one of the twelve families
  this node was asked for; recorded so its existence is not lost.

Both are captured in `FINDINGS.json` under `adjacent_captured_feeds_not_in_the_field_list`, with row
counts and spans measured, not quoted.

---

## 6. Contradictions found

**6.1 — `possession_features.py` calls `is_playoff_game` "a schedule fact, known at the cutoff"; the
bytes carry no observation supporting that.** Line 58 of `possession_features.py` documents
`is_playoff_game` that way, and line 318 derives it as `(season_type == "Playoffs")`. `season_type`
reaches the frame from `team_possession_prior_v1.parquet`, which took it from `master_team`, whose
`observed_time` is a 2026 bulk scrape on **2,982 of 2,982** universe rows. The claim is almost
certainly true in substance and is unsupported by any timestamp in any file. This is a
document-versus-bytes contradiction and it is reported, not reconciled. See section 7.

**6.2 — `data/reference/tip_times.csv` and `prediction_contract_v4/game.parquet` disagree about
whether the tip time was knowable.** The first covers 1,219 games with no observation timestamp
retained; the second admits 407 games under an explicit `observed_at < tip - 90 min` screen. Both are
in the repository, both describe the same quantity, and only one of them can be cited for
cutoff-validity. `prediction_contract_v2.py` documents that an earlier version imputed
`observed_at = tip - 7 days` and that this was removed as "pure manufacture of availability";
`tip_times.csv` does not impute, but by keeping only the latest snapshot it reaches an equally
unusable place by a different route.

**6.3 — `features/common.py::TZ_OFFSET` has no key for `PHX` or `PDX`.** The map (lines 52-58) holds
`PHO` and `POR`. Measured from `master_team`: `PHX` appears from 2025 (55 team-games in 2025, 29 in
2026) and `PDX` from 2026 (29 team-games); `PHO` and `POR` do not appear after 2024. Any feature
routing an abbreviation through `TZ_OFFSET` on a 2025 or 2026 row therefore yields NaN for Phoenix
and Portland. The module's own comment ("post-2024 franchises never appear in the screening window;
mapped for safety") shows the authors were aware of the boundary, so this is a **latent trap for any
re-run on 2025-2026 data**, not a defect in results already produced. It is also a quantity
mismatch: `TZ_OFFSET` is a fixed relative-hours map with no DST resolution, which is not the same
object as `timezone.venue_utc_offset_hours` in this ledger.

**6.4 — the possession universe's 8 missing rows are not scattered; they are the 2021 opening day.**
`master_team` holds 2,990 team-game rows, the possession universe 2,982. The difference is **exactly
the four games of 2021-05-14** (`1022100001`-`1022100004`), all eight team-games, enumerated in
`FINDINGS.json` under `cross_artifact_row_reconciliation.excluded_rows`. The pace producer has no
prior-games evidence at all on the opening day of the first season in the archive, so those rows
carry no projected exposure and fall out. **Every coverage figure in this ledger is therefore
computed on a universe that already excludes the single hardest cold-start day in the data, which
flatters any prior-games-only field by construction.** The arithmetic was known (2,982 of 2,990);
that it is precisely opening day 2021 is stated here because the two are not the same fact.

The measurable consequence: `roster.prior_in_season_box_membership` is covered on 2,914 rows while
`rest.days_since_prev_game` is covered on 2,906. The 8-row gap is the same 8 rows — `master_player`
knows of a prior 2021-05-14 game that the possession universe does not contain, so 8 of the
universe's season openers look like non-openers to a `master_player`-based derivation and like
openers to a universe-based one. **Two honest derivations of "is this a season opener" disagree by 8
rows depending on which artifact defines "prior".**

---

## 7. Stop conditions — raised, not resolved

The node's stop condition is: *a finding that would change the primary target, the K0 structure, the
inference structure, the candidate universe, the cutoff-valid feature set or the leakage status —
HALT and raise, do not resolve it inside the node.* Three findings touch it. **I have changed
nothing and reclassified nothing.**

**S-A. The rule this node was given is stricter than the rule the possession feature contract
operates under, and applying it literally would move declared possession features out of the
cutoff-valid set.** `possession_features.py` declares four features — `pace_gap`,
`pace_evidence_depth`, `opp_pace_evidence_depth`, `is_playoff_game`. Their cutoff-validity rests on
**construction-order attestation**: the frozen pace producer used prior games only, and
`PROJECTED_EXPOSURE_RECEIPT.json` / `PROJECTED_EXPOSURE_VALIDATION.json` validate that 35/35. Under
this node's rule — *a field with no source timestamp is CUTOFF_UNPROVEN* — all four are UNPROVEN,
because `team_possession_prior_v1.parquet` carries no per-row capture timestamp and `season_type`
traces back to a 2026 bulk scrape. This ledger records them as CUTOFF_UNPROVEN **within the ledger's
own vocabulary**, with `structural_class` `frozen_producer_prior_games_only`, and explicitly does
**not** assert that the possession feature set is inadmissible. The program must decide whether
"validated construction order" and "timestamped observation" are the same standard. **They are not
the same standard, and this node is not authorised to pick one.**

**S-B. The candidate universe excludes exactly the 2021 opening day (6.4).** Any statement about
cold-start coverage computed on this universe is computed on data with the worst cold-start day
removed. That is a property of the candidate universe and is raised rather than adjusted.

**S-C. The declared cutoff policy makes the one real availability feed unusable on the majority of
games (4.5).** `date_only_prior_day_cutoff` at 18:00 UTC the prior day precedes the publication of
official pregame availability reports. 2 of 12 overlapping rows clear. This is a standing property
of the policy, not of the data, and changing the policy would change the cutoff-valid feature set —
so it is raised, not changed.

---

## 8. What I could NOT establish, and why

1. **Whether any 2021-2024 field was actually observable pregame.** No artifact in the repository
   carries a pre-cutoff observation timestamp for any of the twelve families before the 2025 season.
   Absence of a timestamp is not evidence of unavailability in the world — it is evidence that this
   repository cannot prove availability. `CUTOFF_UNPROVEN` says exactly that and nothing stronger.
2. **Whether `tip_times.csv` could be repaired into a cutoff-valid artifact.** The underlying odds
   tables carry `odds_snapshot_timestamp` and `collect_bios.py::load_odds` reads it; the writer drops
   it. I did not open the odds tables to measure how many of the 1,219 games would survive an
   `observed_at < tip - 90 min` screen, because that is a rebuild of a source artifact and outside
   this node's write scope. The **407-game** figure from `prediction_contract_v4` is the only
   screened number I can stand behind, and it may be a floor rather than a ceiling.
3. **The true venue of any game.** With `sched.neutral_site_flag` ABSENT, I can measure that the home
   team's arena is what every venue/travel/elevation/time-zone field resolves to; I cannot measure
   how often that is wrong. No source in the repository could settle it.
4. **Whether any transaction was public before its effective date.** `publication_time` does not
   exist and the raw scraped HTML is gitignored and absent, so no diff against a re-scrape is
   possible. `ROSTER_SOURCE_AUDIT_RECEIPT.json` reaches the same conclusion; I re-confirmed the
   file's schema and could add nothing to it.
5. **Actual travel.** `travel.km_from_prev_venue` is a schedule-order great-circle surrogate at
   city-level precision. No itinerary, flight, charter, departure, arrival or lodging record exists
   anywhere in the repository, so real travel burden is unmeasurable here and I did not proxy it
   further.
6. **Player-level injury coverage before 2026-07-30.** The wire's did-not-play rows carry an
   effective date but no publication time, so I can report that a DNP record exists for a team-date
   and cannot report that it was knowable at that date's cutoff.
7. **Anything about comparative performance.** Not attempted, by rule. Nothing under
   `stage2b/SEALED_RESULTS/` was opened.

---

## 9. Reproduction

```
python experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py
python experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/TESTS.py
python -c "import json;json.load(open('experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json'))"
```

`build_ledger.py` prints the field count and verdict tally and rewrites `FINDINGS.json`. `TESTS.py`
returns 0 on success (pytest is not installed; repo convention is a standalone script with `main()`
returning 1 on failure) and currently prints:

```
PASS - 52 fields, 5 folds, 2982 team-game rows / 1491 clusters
       verdicts: {'CUTOFF_UNPROVEN': 37, 'ABSENT': 7, 'CUTOFF_VALID': 5, 'CUTOFF_INVALID': 3}
```

`TESTS.py` checks, among other things, that: the epistemic-status line survives verbatim; the
universe is 2,982 / 1,491; every universe game is bound to a `forecast_cutoff`; `cutoff_valid` is a
strict subset of `covered` in every cell; the season partition exhausts the universe and its
per-season counts sum back to the overall counts; **no field with verdict CUTOFF_UNPROVEN,
CUTOFF_INVALID or ABSENT carries a positive cutoff-valid count anywhere**; no field with verdict
CUTOFF_VALID lacks a named per-row timestamp column; and every fold's train and test row counts are
even, which is the arithmetic signature of no game cluster having been split across the boundary.

All input files are hash-pinned in `FINDINGS.json` under `sources` (sha256 of the exact bytes read).
Note that `data/injury_capture/injury_log.csv` is under active live capture at the repository root
on a different branch; the bytes measured here are the worktree's (sha256 `f3ad40b9...`, 551 rows),
and a later capture will legitimately produce different numbers.

---

## 10. One thing this report must not be read as saying

Nothing here admits any field into any model. Several fields are 100% available and a few are
cutoff-valid. **Availability is not eligibility and eligibility is not admission.** Admission
requires a registered experiment, a matched per-arm K0, clustered inference and a gate invocation,
none of which this node performed or is authorised to perform.
