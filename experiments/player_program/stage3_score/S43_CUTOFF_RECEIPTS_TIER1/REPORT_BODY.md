# S43_CUTOFF_RECEIPTS_TIER1 — tier-1 cutoff-validity provenance receipts for ten schedule-fixed fields

**Commissioned by:** user decision D065. **Discharges:** part of S37 audit finding A9 (Severity A).

**Epistemic status:**

> PROVENANCE RECEIPT. A demonstration that each field's VALUE is fixed by the schedule before tipoff rather than computed from observations, plus the producing job and its as-of bound. NOT a per-observation timestamp audit. No fitting; no performance number of any kind; counts, censuses, hashes and provenance only.

**Root.** The program worktree
`C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`, and only it.
`data/masters/master_team.parquet` was verified to hash to the pin `ad79ce5cdda7e058…`;
the known-drifted live copy `e8e35b539df2d13f…` is refused **by
name**, as `runner/universe.py:71-73` does, not merely by pin failure.

**Write scope.** Everything this node produced is inside
`experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER1/`. No file outside it was
modified, no frozen artifact was edited, and no git command was run.

**Outputs.** `RECEIPTS.json` (machine-readable, one object per field), this report, and the two
scripts that produced them. Reproduce with:

```
python experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER1/MEASURE_TIER1_PROVENANCE.py
python experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER1/EMIT_REPORT_BODY.py
```

Every number below is interpolated from `RECEIPTS.json` by `EMIT_REPORT_BODY.py`, never retyped, so
the prose cannot drift from the measurement.

---

## 1. The standard being applied, and whose it is

D065, verbatim on the standard:

> "Opponent, home/away, season type, scheduled rest/B2B/3-in-4, venue/timezone: these should require only a cheap provenance receipt showing they derive from information fixed before tipoff. ... So don't turn 12 fields into 12 research projects. Establish the minimum sufficient proof for each field, record it, and unblock fitting."

The tier-1 discriminator is therefore: **is the value fixed by the schedule before tipoff, or is it
computed from observations?** Tier 1 is the former. This is a provenance demonstration, not a
per-observation timestamp audit.

Per the coordinator addition to D065, a tier-1 receipt must not merely argue that the concept is
schedule-fixed. For each field it must state the **producing job**, that job's **as-of bound**, the
**provenance chain**, and **sha256 of every file read as evidence**. The rationale, recorded because
it is the reason the addition exists:

> A cheap provenance receipt proves the CLASS of a field, not the integrity of the pipeline that produced it. If a tier-1 field is materialised by a job that happens to backfill from a later source, a concept-only receipt would not catch it. Naming the producing job and its as-of bound closes most of that gap at no extra cost.

That addition earned its keep here. See section 4.

---

## 2. The D10 ledger's objection, engaged rather than evaded

The D10 field-availability ledger rules all ten of these fields `CUTOFF_UNPROVEN`, and it says why,
on the timezone table (`build_ledger.py:360-366`):

> "The values are time-invariant in substance, but time-invariance is an argument, not a timestamp,
> and this ledger does not accept arguments in place of evidence."

The D10 ledger says, on the timezone table: 'The values are time-invariant in substance, but time-invariance is an argument, not a timestamp, and this ledger does not accept arguments in place of evidence.' (build_ledger.py:360-366). That objection is not withdrawn and is not refuted here. Under user decision D065 the standard of proof for THIS CLASS OF FIELD is changed: for tier-1 fields a provenance argument PLUS a named producing job with its as-of bound stated IS now sufficient. The ledger's CUTOFF_UNPROVEN verdicts stand as verdicts under the ledger's own rule; this receipt does not edit them and did not write to the ledger. What it records is that the program's standard of proof for these ten fields is now the one the user set, not the one the ledger applied.

Stated plainly so it cannot be misread later: **these receipts are a ruling about the standard, not
a discovery that the ledger was wrong.**

---

## 3. Universe the receipts are measured on

Rebuilt exactly as `runner/universe.py::build_universe` (lines 127-143) does it: `is_home == 1`
clusters, excluding the D010 date `2021-05-14`.

| quantity | measured |
|---|---:|
| game clusters | 1,491 |
| team-game rows | 2,982 |
| Regular Season rows / clusters | 2,770 / 1,385 |
| Playoffs rows / clusters | 212 / 106 |
| distinct team_ids | 15 |
| O2 pre-build game_id digest | `e0083be22b32ddf5…`, re-derived here and **matching** `PREBUILD_GAME_ID_DIGEST.json` |

Per-season clusters: 2021 205, 2022 239, 2023 260, 2024 262, 2025 310, 2026 215. Only two
season types occur (`Regular Season`, `Playoffs`); no Preseason or All-Star row is in the universe.

`master_team.parquet` carries an `observed_time` column that is a **local file mtime in mid-2026**,
not an as-of bound. It is dropped immediately after read, before any downstream use, and **no frame
was written to disk at all** — every output of this node is JSON aggregates and this prose.

---

## 4. The as-of bound finding, which is the substantive result of this node

Three producing jobs cover all ten fields. Their as-of bounds are not alike, and one of them is
honestly absent.

### 4.1 `build_masters.py` — **NO AS-OF BOUND**

`build_masters.py` takes no as-of argument, no cutoff, no date bound and no snapshot id. It globs
whatever is present under `data/refresh_2026/gamelog_*.parquet`,
`data/wnba_gamelog_{2021..2024}.parquet`, `data/wnba_team_gamelog_2024.parquet`, the per-game
misc/advanced directories and `data/shotcharts/shots_*.parquet`; reads each in full; and records
`observed_time = max(local file mtime of the contributing files)` (`:118-120`, `:594-595`). Every one
of those artifacts is a **completed-game record** and every mtime is a 2026 bulk scrape.

**This receipt does not claim an as-of bound for `build_masters.py`, because it does not have one.**
This is exactly the case the coordinator addition was written to catch, and it is stated rather than
finessed.

What makes the five `master_team` schedule columns tier-1 is therefore **not** a bound on the job. It
is that the job derives them from **game identity** and never from any quantity produced by the play
of the target game:

* `season` and `season_type` are **pure functions of the `game_id` string**;
* `opp_team_id` is the **set complement** of the row's own `team_id` within its `game_id` cluster;
* `is_home` is the **MATCHUP orientation token** (`" @ "`) or the shotchart HTM/VTM role.

No box-score statistic, score, minute or outcome enters any of them. A later re-scrape could only
change these values by changing the league's own identity record of the fixture.

For `sched.is_home` the as-of gap is at its widest, and the receipt says so in terms: the
orientation token is read off a completed-game box score or shot chart. The receipt asserts the
**class** and names the **producing job**; it does not and cannot assert that the bytes read were
captured before tipoff.

### 4.2 `runner/universe.py::build_universe` — **byte-bounded, not time-bounded**

It refuses to build unless `master_team.parquet` hashes to the pin (`:64-77`), refuses the
known-drifted live copy by name (`:71-73`), and refuses to return a frame unless the built `game_id`
set re-derives to `PREBUILD_GAME_ID_DIGEST.json` (`:80-90`, `:136-140`). That is a **reproducibility
bound, not an as-of bound**, and it is reported as such. It was verified live: the digest re-derived
and matched.

### 4.3 `collect_bios.py::phase_cities` — **offline and unbounded by construction**

`data/reference/collect_bios.py::phase_cities` (`:201-224`) performs no network read and no data read
that can supply a value. It materialises `team_cities.csv` from the `CITY_ROWS` **literal in its own
source** (`:180-198`), hand-entered 2026-07-31 at city-level precision (`:172-179`). Its only read of
repository data is `master_team.parquet` for join **verification** (`:210-218`), which can fail the
build closed but cannot inject a value.

This reframes the D10 complaint. The ledger objected that the file has "no capture timestamp of any
kind — no column, no sidecar manifest, no fetch record." That is correct and, on this reading,
**expected: there is no capture.** The value's provenance is the producing job's source code, which
is a *stronger* bound than a capture timestamp would be, because it is fixed for every row of every
season simultaneously.

---

## 5. The receipts

All ten are issued. Verdict `TIER1_RECEIPT_ISSUED` in every case. Full provenance chains, per-field
evidence hashes and residual-risk statements are in `RECEIPTS.json`.

| # | field | tier assigned by | producing job (as consumed) | as-of bound | verdict |
|---|---|---|---|---|---|
| 0 | `sched.game_id` | **coordinator** | `build_masters.py` (`:355`, `:600-607`) + `universe.py:131-140` | none (job) / byte-pinned (universe) | ISSUED |
| 2 | `sched.season` | **coordinator** | `build_masters.py::season_of` `:110-111`, applied `:572` | none — but the column is a pure function of `game_id` | ISSUED |
| 3 | `sched.season_type` | user | `build_masters.py::stype_of` `:114-115` + `:80-81`, applied `:573` | none — pure function of `game_id` | ISSUED |
| 4 | `sched.is_home` | user | `build_masters.py::build_game_index` `:319-325`, `:345-370`, merged `:568-570` | **none — widest gap; see 4.1** | ISSUED |
| 5 | `sched.opp_team_id` | user | `build_masters.py::build_game_index` `:386-391`, merged `:568-570` | none — reads no source beyond cluster membership | ISSUED |
| 9 | `rest.is_back_to_back` | user | `sc06_sched_fatigue_diff.py::fatigue_index` `:91-96` (**in-frame; no materialised column**) | byte-pinned universe | ISSUED |
| 10 | `rest.games_in_prev_7_days (3-in-4 class)` | user | `sc06_sched_fatigue_diff.py::fatigue_index` `:92-97` (**in-frame**) | byte-pinned universe | ISSUED |
| 12 | `venue.venue_team_id` | user | `sc06_sched_fatigue_diff.py:100-101` (**in-frame**) | inherits #4 and #5; no new source | ISSUED |
| 18 | `timezone.venue_iana_timezone` | user | `collect_bios.py::phase_cities` `:201-224` from `CITY_ROWS` `:180-198`; read by `sc06:73-81` | offline; value is a source-code literal | ISSUED |
| 22 | `timezone.shift_from_prev_venue_hours` | user | `sc06_sched_fatigue_diff.py:99-105` (**in-frame**) | inherits #12 and #18; no new source | ISSUED |

**A finding worth naming on its own:** five of the ten fields (#9, #10, #12, #22, and #18's consumed
form) have **no materialised column anywhere in the repository**. They are derived in-frame by
`sc06_sched_fatigue_diff.py` from `universe.team_rows`. The producing job for those fields *is the
arm module*. Nothing backfills them, because nothing stores them.

### 5.1 Identity tests — every one returns zero violations

These are censuses over all 2,982 rows. A test returning zero violations
demonstrates that the column **is** the schedule-fixed quantity it is claimed to be. It does not, and
cannot, demonstrate anything about *when* the bytes were captured.

| test | rule | violations |
|---|---|---:|
| `season` | `season == int("20" + game_id[3:5])` | **0 / 2,982** |
| `season_type` | `season_type == SEASON_TYPE_BY_DIGIT[game_id[2]]` | **0 / 2,982** (0 `Unknown`) |
| `opp_team_id` | is the other `team_id` in the same cluster | **0 / 2,982** |
| `opp_team_id` | never equals own `team_id`; never null | **0 self-referential, 0 null** |
| `is_home` | domain ⊆ {0,1}; no nulls | **0 null** |
| `is_home` | exactly one home row per cluster | **0 / 1,491 clusters** |
| `game_id` | 10 characters, all digits | **0 / 2,982** |
| `game_id` | exactly two team rows per cluster; no duplicate (game_id, team_id) | **0 bad clusters, 0 dupes** |
| `venue_team_id` | equals the cluster's home team | **0 / 2,982** |
| `venue_iana_timezone` | resolves every row; every zone in the arm's pinned map | **0 unresolved, 0 unmapped** |

`game_id` digit 2 takes only the values `2` (Regular Season) and `4` (Playoffs),
matching `season_type` on every row. All 15 universe
`team_id`s are present in `team_cities.csv`
(16 rows,
15 ids — PHO and PHX share id
1611661317); its sha256 `10a544fdc52a9c80…` matches the hash the D10 ledger
itself cites. 6 IANA zones
occur on the universe, all of them in SC06's pinned `STANDARD_OFFSETS`; the arm fails closed on any
zone outside it (`sc06:78-79`).

### 5.2 Consumed censuses

Counts only. No performance quantity of any kind was computed.

* `rest.is_back_to_back`: **89** true
  rows. Career clock and same-season clock give the **same
  89** and disagree on
  **0 rows** — a cross-season gap
  is never exactly one day. This independently confirms S37 finding B1's statement that the two rest
  components evaluate identically across an off-season gap and the B1 defect is confined to the
  travel term.
* `rest` 3-in-4 (as consumed by SC06):
  **88** true rows;
  30 rows have fewer than
  two previous games.
* `rest.games_in_prev_7_days` (the ledger's literal quantity):
  0→136, 1→475, 2→1,319, 3→1,018, 4→34.
* `tz_crossed` (as consumed): non-zero on
  **1,310** rows;
  values 0.0→1,672, 1.0→748, 2.0→323, 3.0→239.
  Career vs same-season clocks disagree on
  **30**
  rows — exactly the 30 team-game rows S37 finding B1 measured, independently reproduced here.

### 5.3 Reconciling `tz_crossed` to the ledger's published number

The D10 report publishes `timezone.shift_from_prev_venue_hours` as non-zero on
**1,103** of 2,982 rows. The consumed quantity
reads **1,310**. A reader must be able to
see why, so it was decomposed:

| reading | non-zero rows |
|---|---:|
| D10 ledger, published | 1,103 |
| **re-derived here**: same-season clock, DST resolved via `zoneinfo` | **1,103** ✅ exact match |
| career clock, DST resolved | 1,129 (+26, the cross-season openers) |
| career clock, standard offsets — **the consumed reading** | 1,310 (+181) |

The final increment is exactly the count of rows whose venue and previous venue are the
`America/Phoenix` ↔ `America/Los_Angeles` pair:
**181**.
America/Phoenix does not observe DST, so under zoneinfo it coincides with America/Los_Angeles at -7 throughout the WNBA season and the shift reads ZERO; under the arm's pinned STANDARD-offset map the two differ by one hour and the shift reads ONE. This is a definitional divergence between two readings of ledger #22, not a cutoff-validity question, and it is recorded rather than reconciled.

The exact reproduction of the ledger's 1,103 is a useful side
effect: the D10 number replicates.

---

## 6. COORDINATOR-ASSIGNED TIER

**Two of the ten fields were not named by the user. They were assigned to tier 1 by
coordinator #04.**

| field | ledger # | ground for the assignment |
|---|---|---|
| `sched.game_id` | 0 | the league's own fixture identifier, issued at schedule release; not computed from observations |
| `sched.season` | 2 | literally `int("20" + game_id[3:5])` — a pure function of the identifier, measured to hold on 2,982 / 2,982 rows |

The user's D065 tier-1 list named:
**opponent, home/away, season type, scheduled rest/B2B/3-in-4, venue/timezone**. `game_id` and `season` are
not on it.

Recorded explicitly so the user can overrule the assignment cheaply. If overruled, these two fields return to the A9 unreceipted set and this node's other eight receipts are unaffected.

---

## 7. The `shift_from_prev_venue_hours` tension, recorded not papered over

`timezone.shift_from_prev_venue_hours` (ledger #22) is schedule-derived **and yet depends on the
previous game having been played.** Its value on row *r* is a function of the team's previous row in
the *resolved universe*, and that row is only known to be the previous row once that game has been
played and resolved in. Under the published schedule alone the previous fixture — and hence the
shift — is also determined; the two coincide **except where a fixture was postponed or
displaced.**

**The user's explicit naming of "venue/timezone" in the D065 tier-1 list settles this field as
tier 1.** The tension is recorded here so that the settlement is visible as a *ruling* rather than as
an omission. Absent that naming, this field would have gone to RAISE-DO-NOT-ASSIGN below.

Consequences that follow and are not closed by this receipt:

1. Like the rest fields, #22 **inherits M_A1's enumerated `game_date` exception set** — the 10
   release-order displaced clusters plus the 6 with no second-endpoint witness.
2. SC06 already carries an **A1-SENSITIVITY kill** for precisely this dependency (`sc06:178-180`).
   S37 finding **B3** records that the kill cannot fire, because the enumerated exception set is
   never read by any code. Wiring it converts this tension from an assumption into a measured
   sensitivity, and needs no new data.
3. The career-vs-same-season clock ambiguity (S37 **B1**) touches this field and only this field
   among the ten, on
   30
   rows, measured above.

---

## 8. RAISE-DO-NOT-ASSIGN

Assigning a tier **is** deciding the standard of proof, and D065 reserves that judgement to the user.
Three boundary cases were found. **No field was reassigned and no receipt was narrowed on account of
them.**

### R1 — playoff rows: the discriminator's two clauses come apart

**Concerns:** `sched.season_type`, `sched.opp_team_id`, `sched.is_home`, `venue.venue_team_id`, `timezone.venue_iana_timezone`, `timezone.shift_from_prev_venue_hours` — **playoff rows only.**
**Census:** 212 of 2,982 team-game rows
(7.11%), 106 of
1,491 clusters; by season
2021 17, 2022 23, 2023 20, 2024 22, 2025 24, 2026 none (the 2026
season is partial).

The user's tier-1 discriminator was stated as: 'is the VALUE fixed by the schedule before tipoff, or is it COMPUTED FROM OBSERVATIONS? Tier 1 is the former.' On playoff rows BOTH clauses are true at once. Which teams meet, which of them hosts, in which arena and in which time zone are all determined by regular-season standings and prior series RESULTS -- i.e. computed from observations -- and are nonetheless fixed before that particular game's own tipoff. The two halves of the discriminator do not partition these rows.

**What this node believes but did not act on:** The literal tier-1 standard as written ('derives from information fixed before tipoff') is MET on playoff rows, because prior-game results are fixed before this game's tipoff and are legitimately available to a strictly-prior model. On that reading no change is needed. The flag exists because the user's SECOND clause ('computed from observations') would, read alone, exclude them.

**Cheapest possible ruling** — One sentence: 'for tier-1 purposes, information determined by the outcomes of games that were themselves completed before this game's cutoff counts as fixed before tipoff.' If the user agrees, R1 closes with no further measurement.

### R2 — "scheduled" versus "as played"

**Concerns:** `rest.is_back_to_back`, `rest.games_in_prev_7_days`, `timezone.shift_from_prev_venue_hours`, on all rows.

The user's tier-1 list said 'scheduled rest/B2B/3-in-4'. No SCHEDULED-date artifact exists in this repository -- D10 section 4.1 measured that the only artifact carrying the schedule is a completed-game box score. Every rest and previous-venue quantity in this slate is therefore computed from AS-PLAYED dates. The two agree except on postponed or displaced fixtures, which is precisely the population M_A1 enumerated as its exception set.

Ruling that as-played dates satisfy a 'scheduled' tier-1 standard would change the standard of proof, which is the user's to set. This node records the substitution instead of assuming it away.

**What would close it cheaply:** Either (a) the user rules that as-played dates are an acceptable stand-in for scheduled dates for tier-1 purposes given that M_A1 already enumerates the divergent clusters, or (b) SC06's existing A1-SENSITIVITY kill is actually wired (S37 finding B3 records that it currently reads nothing), which converts the substitution from an assumption into a measured sensitivity. Option (b) needs no new data.

### R3 — ledger #10 denotes two different quantities

**Concerns:** `rest.games_in_prev_7_days` — **field identity, not tier.**

Ledger #10 is named 'rest.games_in_prev_7_days' and D10 derives a 7-day count. SC06 consumes a 3-in-4 indicator. The S37 A9 table papers this over with the parenthetical '(the 3-in-4 class)'. They are different quantities and only one of them is consumed by any arm. This receipt covers the 3-in-4 indicator that SC06 actually consumes and counts both.

Deciding which quantity ledger #10 denotes is a contract question, not a measurement. It does not change either field's tier -- both are schedule-derived -- but it changes what the receipt is a receipt FOR.

---

## 9. What these receipts do NOT establish

1. **That any of the bytes were captured before tipoff.** For the five `master_team` schedule
   columns the producing job has no as-of bound and reads only completed-game artifacts. The receipt
   establishes class and names the job; it stops there, deliberately.
2. **That the venue is the home team's arena.** `sched.neutral_site_flag` is ABSENT from the entire
   repository (D10 `build_ledger.py:262-270`). `venue.venue_team_id` and
   `timezone.venue_iana_timezone` mean "the home team's" venue and zone, not "the venue used". This
   is an **accuracy** gap, not a cutoff-validity gap, it is load-bearing for four families, and no
   source in the repository could settle it.
3. **The correctness of `game_date` or of the `(game_date, game_id)` sequencing.** That rests on
   ledger #1, which has its own measurement (`M_A1_GAME_DATE_CUTOFF_V2`) and its own 16 enumerated
   exception clusters. `sched.game_id`'s receipt does not extend to it.
4. **Anything about the other three A9 items.** `opponent.opp_pace_estimate` (#50),
   `opponent.prior_box_aggregates` (#51) and the five `score_baseline_rows` prediction columns are
   outside this node's ten and are untouched. **A9 is only partly discharged.**
5. **Anything comparative.** No fit, no arm-vs-null comparison, no performance number. Nothing under
   any sealed-results tree was opened.

---

## 10. Evidence — sha256 of every file read

| sha256 | file (repo-relative) |
|---|---|
| `ad79ce5cdda7e058…` | `data/masters/master_team.parquet` |
| `10a544fdc52a9c80…` | `data/reference/team_cities.csv` |
| `56339a41ffdcb0ea…` | `data/reference/collect_bios.py` |
| `58e057cddb4bf702…` | `build_masters.py` |
| `1f68cbe0c1463971…` | `experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/arms/sc06_sched_fatigue_diff.py` |
| `cfad507ac7243200…` | `experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/runner/universe.py` |
| `c2e46f47290d2185…` | `experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/runner/runner_constants.py` |
| `539a07a174197e04…` | `experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/PREBUILD_GAME_ID_DIGEST.json` |
| `70f1d937e5267bda…` | `experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py` |
| `72ee04f2b99d6835…` | `experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json` |
| `c45074d488f1dc49…` | `experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/REPORT.md` |
| `de28ec24de55bb3f…` | `experiments/player_program/stage3_score/S37_IMPLEMENTATION_AUDIT/S37_REPORT_BODY.md` |
| `552246ccdc86d358…` | `experiments/player_program/stage3_score/S37_IMPLEMENTATION_AUDIT/SPEC.json` |
| `263bf366c63cb9da…` | `experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/MEASURE_A1_DATE_WITNESS.py` |

Full-length digests are in `RECEIPTS.json` under `evidence_sha256_all_reads`, and per-field under
each record's `evidence_sha256`.

---

## 11. One thing this report must not be read as saying

Nothing here admits any field into any model, and nothing here promotes a D10 ledger record. Ten
fields now carry the tier-1 provenance receipt D065 called for. **Availability is not eligibility and
eligibility is not admission.** Whether these receipts discharge S30 §8 for these ten fields
— and therefore whether A9's halt lifts for them — is the coordinator's and the user's call,
not this node's.
