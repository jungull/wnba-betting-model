# M36 — the props seam: the p_active wiring is blocked by plumbing, not by data

**E0-style diagnostic, NON-CLAIMING.** Nothing here fits, scores or adopts a model. No
wager-shaped claim; S42 untouched.

The handoff names one live, sized, unbuilt improvement: wire the injury tape into `p_active`
at T−90m, measured by M35 at **+15.2%** on appearance Brier. This asks why it cannot be built
today, and whether that reason is durable.

---

## 1. The boundary is real, and M35 was right about it

| | range | rows |
|---|---|---|
| arm's scored frame (`translation_rows.parquet`) | 2024-05-14 .. **2026-07-30** | 5,889 |
| injury tape (`injury_snapshots.csv`) | **2026-08-06** .. 2026-08-22 | 11,869 |

**Zero overlap, separated by seven days.** M35's statement that "the outcome snapshot and the
capture do not overlap" is precise and holds. The improvement cannot be measured against the
shipped `p_active` because the arm has never been scored on a single day the tape covers.

Note what this is *not*. Outcomes are not the constraint: `master_player.parquet` runs to
2026-08-21 and carries **1,085 player-game rows over 45 games and 16 dates** inside the tape
window, including ~192 zero-minute rows, so the negative class exists. Truth is available. It
is the *arm's predictions* that stop early.

## 2. The cause is a source boundary, not a collection failure

M13 reads `master_props_historical.csv` **exclusively**, under `D027_PROPS_HISTORICAL_BOUNDED_USES`.
That archive's last quote is **2026-07-30 22:55:42 UTC**. The frame ends exactly where its only
authorised source ends.

Meanwhile the programme's **own** live props ladder (stood up by D028, tier-bumped by D029) has
been writing `master_props.csv` the entire time:

| | |
|---|---|
| rows | **31,290** |
| coverage | **2026-07-31 .. 2026-08-23** — it begins the day the archive stops |
| events | 54 |
| markets | player_points 11,307 · rebounds 8,003 · threes 6,169 · assists 5,811 |
| books | 5 |

**The August data was never missing. It was captured, and never plumbed in.**

## 3. The seam is crossable on identity — measured, not assumed

The live file has no `game_id`. Resolving events via `(game_date, home, away)` against
`master_team`:

| | |
|---|---|
| unmapped team names | **none** (all 15) |
| events | 54 |
| events on played dates | 47 *(outcomes stop 2026-08-21; the ladder quotes future games)* |
| resolved to exactly one `game_id` | **47** |
| **unresolved** | **0** |
| **ambiguous (multi-match)** | **0** |

Identity resolution is where this programme has been bitten before (E1_I0052), so both failure
modes were counted, not just one. Both are zero.

## 4. The ladder supports a T−90m question

A cutoff question needs quotes standing *before* the cutoff. On `player_points`:

| | |
|---|---|
| quotes | 11,307 over 54 events |
| median lead before tip | **715 min** (~12 h) |
| **standing at or before T−90m** | **10,285 (91.0%) across 53 of 54 events** |
| distinct snapshots per event | median 5 (min 1, max 8) |

## What this changes

The +15.2% is **days of plumbing away, not weeks of collection away**. The prerequisite is not
more capture — it is extending the scored frame across 2026-07-30/07-31 using a source the
programme already owns.

## What it does not settle, and must not be read as settling

- **This does not re-point M13.** `translation_rows.parquet` is untouched and no receipted node
  cites `master_props.csv`. Crossing the seam means citing a source **D027 does not govern** —
  an authorisation decision, not a code change, and not one a feasibility check may make.
- **The staleness semantics differ.** The historical archive carries
  `snapshot_requested_utc`/`snapshot_returned_utc`, a *pair* that bounds staleness. The live
  file carries a single `snapshot_utc`. For self-captured data that instant is arguably cleaner,
  but it is a **different definition**, and it matters precisely because the open question is a
  cutoff question. Reconciling it is prerequisite work, not a footnote.
- **Median 5 snapshots per event is coarse**, and one event has a single snapshot. Adequate for
  "was a quote standing at T−90m"; **not** adequate for any persistence or lead-lag question.
- **Splicing two sources at a date boundary creates a discontinuity** at 2026-07-30/07-31.
  Anything measured across it must test for a level shift at the seam rather than assume none.
- **Nothing here re-measures the +15.2%.** That figure is still M35's, on 701 rows over ten
  dates, against a walk-forward base rate — **not** against the shipped `p_active`. Measuring it
  against the arm is the entire point of crossing the seam, and it has not been done.
- **It does not touch M33's market gap.** That deficit is minutes among players who play.
  Availability is a different target.
