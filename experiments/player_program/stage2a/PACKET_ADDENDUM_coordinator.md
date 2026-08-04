# Evidence-packet addendum — coordinator verification

**Status: HELD OUT of `stage2a/` until every ideation source has finished.**

The frozen packet (`f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e`) must not
change while sources are working, and later sources must not receive evidence selected in
response to an earlier source's idea. Both findings below were raised by the time-series source
and independently verified by me. Writing them into `stage2a/` now would leak one source's
thinking to the four still running, so they are held here and merged at synthesis.

**The frozen packet is NOT edited. These are corrections to how it must be READ.**

---

## Finding 1 — effective n is 1,491, not 2,982 (CONFIRMED)

`projected_team_off_possessions` is computed per GAME and merged onto both team rows.

```
games with a resolved projection       : 1491
games where BOTH sides share ONE value : 1491
games with 2 distinct values           : 0
team-game rows                         : 2982
```

Every game's two sides carry an **identical** projection, so the 2,982 team-game rows contain
**1,491 independent projections**. The error on a game's two rows is not independent — it is the
same projection measured against two realised counts that themselves sum to a game total.

**Consequence for the packet.** The MAE, bias and stratum point estimates stand. Every `n` in
`chronological_possession_error` and `error_strata` overstates independence by a factor of two,
and any interval computed from those `n` values would be too narrow by roughly √2.

**Consequence for Stage 2B.** Comparisons must be **paired on identical games and clustered at
game level**. An unclustered interval would make a null look significant — precisely the class of
error that invalidated earlier work in this program.

## Finding 2 — possession units differ between artifacts (CONFIRMED)

The packet's target is **regulation-equivalent**: `n_off_poss * 40.0 / game_minutes`, per
`build_projected_exposure.build_pace`, which is also what the incumbent projects.

`team_turnover_reconciliation_v1.team_off_possessions` is something else:

```
dtype=int64  all-integer=True  min=66  max=118
matches the RAW possession count exactly : 2990/2990
OT rows all-integer                      : True (132 OT team-games)
```

It is the **raw** count, not regulation-equivalent. On the 132 overtime team-games the two units
diverge by construction — a 45-minute game's raw count is scaled by 40/45 in the packet's target
and not scaled at all in the reconciliation artifact.

**Consequence.** Which unit the operational turnover-team metric consumes is currently
**unresolved**, and it must be settled before any arm is registered. If the downstream metric
consumes raw possessions while the challenger optimises a regulation-equivalent target, the two
are not the same quantity and the experiment would be measuring the wrong thing on the OT subset.

This is cheap to settle by inspection of the downstream path and must be a Phase 0 gate item, not
a discovery during evaluation.

---

## Provenance

Both findings originate with the **time-series and shrinkage** ideation source. I verified each
directly against the frozen artifacts rather than adopting them on report. Credit is recorded
here so the synthesis does not present them as coordinator findings.

---

## Finding 3 — regulation possession durations partition the game clock EXACTLY (CONFIRMED)

Raised by the **pace and coaching** source; verified directly.

```
regulation duration_sec summed per game:
  games 1495 · mean 2400.0000 · sd 0.000000 · min 2400.0 · max 2400.0
  exactly 2400.0 : 1495/1495
```

`N_possessions x mean_duration == 2400` is an **identity**, not a modelling assumption. Durations
add across the two teams; counts do not. The incumbent averages COUNTS, which is a convex-function
error with a determinate sign whenever the two sides' tempos are dispersed — consistent with the
observed `+0.159` aggregate over-projection.

This is the strongest structural argument produced by any source: it makes the incumbent's
aggregation form provably wrong rather than merely unexamined.

## Finding 4 — OT distortion reaches far beyond the 132 OT rows (CONFIRMED)

```
OT games                                              : 66/1495 = 4.415%
team-games whose 10-game window contains >=1 OT game  : 32.8% (n=2914)
```

Because `WINDOW_K=10`, a 4.4% event contaminates **a third of all trailing windows**. Any
OT-handling correction therefore has roughly 7x the leverage the raw OT count suggests.

## Finding 5 — MY PACKET'S AVAILABILITY TABLE IS WRONG on the venue item (CONFIRMED)

Raised by the **opponent and environment** source. I declared the venue table `ABSENT`. It exists:

```
data/reference/team_cities.csv : 16 rows
  team_id, abbreviation, franchise, first_season, last_season, city, arena, lat, lon, elevation_ft
data/reference/tip_times.csv   : 1219 rows (of 1495)
  game_id, season, game_date, home_team_id, timezone, tip_utc, tip_local, tip_hour_local, tip_dow_local
```

**This is my error, not the source's.** I swept `data/` for `*coach*` but never for a venue or
reference table, and asserted absence from a search I had not run. Travel and time-zone move from
Category B to **Category A**; tip time stays in **B** on provenance grounds (2021 has zero
coverage and the field is odds-derived rather than as-of).

The frozen packet is not edited. This correction travels with it.

## Finding 6 — head-to-head prior meetings are common (COVERAGE MEASURED)

The pace source reported 70.2%. My independent count over the contract universe:

```
team-games with >=1 PRIOR same-season meeting : 2545/2990 = 85.1%
```

Same conclusion — broad enough to be a real lever — but the figures differ and the discrepancy is
unresolved. Likely a different denominator (resolved rows vs all team-games) or a different
same-season restriction. **The synthesis must not quote either number until reconciled.**

## Finding 7 — `master_team` capture provenance is retrospective (PARTIALLY CORRECTS A SOURCE)

The pace source reported "two distinct `observed_time` values". Measured: **10 distinct values**,
clustered in two bulk windows (2026-07-31 20:42:42–45Z and 2026-08-04 12:30:09–22Z) covering
game dates from 2021-05-14.

The source's headline conclusion stands and its count does not: this is a **retrospective bulk
scrape**, not per-game pregame capture. Any `master_team` column therefore carries revision risk
and is cutoff-valid only under a lag argument, never under a capture argument.

---

## Standing so far

Two sources independently reached the raw-vs-regulation unit mismatch (Findings 2 and the
opponent source's A6). Independent convergence on a measurement-basis defect, from different
lenses, is the strongest signal produced so far — and it is a **blocking Phase 0 question**, not
a hypothesis.

---

## Finding 8 — MY `days_rest` STRATUM IS INVALID (CONFIRMED — my error)

Raised by the **adversarial** source. I computed `days_rest` with `groupby("team_id")` only, not
`groupby(["team_id","season"])`. Every season opener therefore inherited the gap since the
team's LAST GAME OF THE PREVIOUS SEASON.

```
season openers (no within-season predecessor) : 76
their days_rest under MY computation          : median 234 days, max 279
my "7+ days rest" stratum                     : n=164
  of which are season openers                 : 61  (37%)
```

The `-1.435` bias I reported for "7+ days rest" is substantially an **off-season artifact**, not a
rest effect. The adversarial source's reading is correct: that stratum is largely an alias for the
early-season / `pace_level > 1` population, which I already report separately. **Any rest
hypothesis resting on that number is resting on my bug.** The stratum must be recomputed
within-season before it can support or refute anything.

## Finding 9 — `pace_level > 1` is ALGEBRAICALLY EQUIVALENT to `game_no_in_season <= 3` (CONFIRMED)

```
agree: 2982/2982 · off-diagonal: 0
```

Exact, and it follows from `MIN_HISTORY_M = 3` by construction. Two "different" strata in my
packet — `by_pace_level` and `by_game_no_in_season` — are the same partition wearing two names.
Any design carrying both as features is exactly collinear in threshold form, and `feature_gate`'s
linear rank check would not necessarily see it as a threshold.

**Consequence.** Hypotheses targeting "early season" and hypotheses targeting "the fallback tier"
are ONE family, not two, and must be arbitrated against each other rather than each credited
against the incumbent.

## Finding 10 — `game_no_in_season` defect NOT REPRODUCED

The adversarial source reported my `game_no_in_season` wrong on 266 of 2982 rows. I could not
reproduce it:

```
rows differing from (team, season, game_date, game_id) ordering : 0/2990
```

My computation agrees exactly with a deterministic date-plus-game_id ordering. The source may have
used a different tie-break or a different denominator. **Recorded as unconfirmed.** I am not
adopting it, and I am not dismissing the possibility that their definition of correct differs from
mine in a way that matters — it should be reconciled with them directly if the stratum is used.

## Finding 11 — the target is ~98% game-level (SUBSTANTIVELY CONFIRMED, figure differs)

```
within-game |difference| : mean 0.880, sd 0.779
between-game variance    : 14.9884
within-game half-spread variance : 0.1519
game-level share of team-game target variance : 97.78%
```

The opponent source measured a within-game gap of 0.886 (mine 0.880) and the adversarial source a
between-game variance of 14.988 (mine identical). The adversarial source put the game-level share
at 98.99%; I measure **97.78%**. The discrepancy is immaterial to the conclusion and both figures
support it: **almost all of the target's variance is a game-level quantity**, so a side-splitting
arm is chasing ~2% of the variance in a near-random residual.

This independently corroborates the opponent source's decision to propose NO within-game
differentiation arm, and it constrains my own A4/A7.

---

## Finding 12 — MY INJURY VERDICT IS WRONG (CONFIRMED — my error)

Raised by the **roster and cold-start** source. My packet ruled injuries "UNAVAILABLE
HISTORICALLY" after examining `data/injury_capture/` only. A full-span source exists:

```
data/injury_history/injury_history.csv : 8,340 rows
  date range 2021-01-07 .. 2026-07-29  (the ENTIRE contract span)
  categories: missed_game_other 3131, missed_game_injury 2242, signing 1455,
              waiver 795, draft 260, trade 252, contract_suspension 111, front_office 49
  observation-timestamp columns: NONE
```

**This is my second availability error, and the same mistake as Finding 5**: I asserted absence
from a search I had not run.

The source nonetheless kept it in **Category B**, and that judgement is correct: the file carries
**no observation timestamp**, so its cutoff validity rests entirely on `date` being an event date
rather than a compilation date. That is precisely the objection this program raises against
asserted-but-unverified cutoff claims. Availability is established; **cutoff validity is not**.

## Finding 13 — MY SUPPORT AXIS IS BROKEN (CONFIRMED — my error)

`n_history_games` carries two different meanings in one column:

```
team_window_same_season   n=2762  min=3    max=10    (TEAM games)
team_window_prior_season  n= 183  min=10   max=10    (TEAM games, always exactly 10)
league_prior_all          n=  37  min=4    max=1300  (CUMULATIVE LEAGUE games)
unresolved                n=   8  min=0    max=0
```

My `support_bucket` strata are therefore built on an axis that changes units at level 3. The
consequence is direct: my **worst-MAE stratum**, `">10"` with n=23 and MAE 4.538, which I
presented as *abundant* support, is **entirely level-3 rows with ZERO team support**:

```
'>10' bucket: n=23, pace_source = {league_prior_all: 23}
```

I inverted the meaning of my own worst stratum. Any arm selected against that axis would be
selected against a mislabelled variable.

## Finding 14 — level 3 is two populations, one of which cannot recur (CONFIRMED)

```
league_prior_all by season : {2021: 28, 2025: 3, 2026: 6}
unresolved       by season : {2021: 8}
```

36 of the 45 fallback rows are 2021 — an artifact of the repository's history beginning in 2021
(dataset left-censoring), which **cannot recur**. Exactly 9 are genuine expansion cold starts
(2025: 3, 2026: 6). Tuning "the level-3 tier" as one population would fit four-fifths of the
weight against a non-recurring artifact.

---

## Summary of coordinator errors found by the ideation sources

| # | my error | found by |
|---|---|---|
| 5 | venue table declared ABSENT; `team_cities.csv` exists | opponent/env |
| 8 | `days_rest` computed across season boundaries; 61 of 164 "7+ rest" rows are season openers | adversarial |
| 12 | injuries declared UNAVAILABLE; `injury_history.csv` spans the full period | roster/cold-start |
| 13 | `support_bucket` built on a column with two meanings; worst stratum inverted | roster/cold-start |

Four errors, three of them assertions of absence or of meaning that I did not verify. The frozen
packet's **error and bias figures stand** — they are computed from the artifacts, not from these
fields — but four of its **strata** and two of its **availability verdicts** do not.

This is the ideation protocol working as intended: five independent sources reading one frozen
packet found defects in it that the packet's author did not.
