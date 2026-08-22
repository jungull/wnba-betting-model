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
- **The staleness semantics differ — now measured, see s02 below.** Settled, with zero
  exposure on this window.
- **Median 5 snapshots per event is coarse**, and one event has a single snapshot. Adequate for
  "was a quote standing at T−90m"; **not** adequate for any persistence or lead-lag question.
- **The seam discontinuity — now tested, see s03 below.** No roster shift; a real depth shift.
- **Nothing here re-measures the +15.2%.** That figure is still M35's, on 701 rows over ten
  dates, against a walk-forward base rate — **not** against the shipped `p_active`. Measuring it
  against the arm is the entire point of crossing the seam, and it has not been done.
- **It does not touch M33's market gap.** That deficit is minutes among players who play.
  Availability is a different target.


---

# s02 — the staleness semantics, settled

s01 named the single-timestamp difference as prerequisite work. It is now measured.

## What `snapshot_utc` means

Read from the capture source, not assumed: `props_capture_daily.py:197` takes the stamp **once
at the top of `main()`**, before the events list is fetched and before any event request is
issued, then writes it identically to every row of the cycle. So

    snapshot_utc  <=  true retrieval time of every row stamped with it

**The direction is the problem.** A cutoff question asks whether a quote was *held* by an
instant. Because the stamp is at or earlier than true retrieval, using it makes a quote look
available **earlier** than it truly was — the optimistic direction, which can admit a quote whose
true retrieval fell after the cutoff. The archive's `returned` stamp is fail-closed; this is not.

## How far it understates, per cycle

Each event response is written to `raw/props_<event>_<stamp>.json` during its cycle, so
stamp → last write is a direct per-cycle upper bound.

| | minutes |
|---|---|
| median | **0.06** |
| p95 | 0.40 |
| max, excluding two outliers | **1.29** |
| max, all cycles | 378.97 |

Two cycles exceed 5 minutes (379.0 and 97.6 min) and **both are day-one, 2026-07-31**. They were
**kept and charged to their own rows**, not dropped and not spread across every row — applying a
global worst case would have manufactured a false 28% exposure.

## Does it leak?

| | |
|---|---|
| player_points rows | 11,307 |
| rows with no raw JSON to bound | **0** |
| admitted at T−90m using `snapshot_utc` | 10,285 |
| admitted using the fail-closed bound | **10,285** |
| **wrongly admitted** | **0 (0.000%)** |

**Why zero:** the capture cadence is coarse, so nothing lands near the boundary — 0 quotes have
a lead in [90, 105) minutes; the nearest admitted quote has ≥120 minutes.

## What this does and does not clear

It **clears** the staleness item as a blocker for a T−90m question on this window.

It **does not generalise.** A finer capture cadence, or a cutoff nearer tip, would put quotes
next to the boundary and the bound would have to be re-measured. The defect is dormant here, not
absent — and the correct long-run fix is to stamp retrieval per response rather than per cycle.

It also leaves the remaining s01 caveats untouched: the seam discontinuity at 2026-07-30/07-31
still needs a level-shift test, 5 snapshots per event is still too coarse for any persistence
question, crossing the seam still cites a source D027 does not govern, and the +15.2% is still
M35's figure against a base rate rather than against the shipped `p_active`.


---

# s03 — the seam discontinuity, tested

## The design limit, stated before the result

The archives **do not overlap**: historical ends 2026-07-30, live begins 2026-07-31. Source and
date are therefore **confounded**, and no statistic fixes that. A seam step inside the normal
day-to-day churn is *absence of evidence for a shift*, not evidence of its absence.

Book composition is the exception — it is a property of the capture configuration, not of the
games, so a change in it across the seam is a source effect by construction.

## Roster: no shift

| | books |
|---|---|
| historical, **2026 season** | 5 — betonlineag, betrivers, draftkings, fanduel, williamhill_us |
| live | 5 — **identical set** |

**A correction worth recording.** Comparing the *whole* historical file (2024–2026) shows 9 books
and implies four were lost at the seam (betmgm, bovada, fanatics, unibet_us). That comparison is
wrong: those books left earlier in history, not at the seam. **The season-matched comparison is
the correct one, and it shows no roster change.**

## Seam step vs ordinary day-to-day step

Ordinary steps computed *within* each source only, never across the seam:

| quantity | last hist | first live | seam step | percentile of within-source steps |
|---|---|---|---|---|
| books | 5.000 | 5.000 | 0.000 | 0.0% |
| overround | 0.066 | 0.069 | +0.002 | 83.1% |
| line | 12.500 | 14.500 | +2.000 | 66.3% |

Nothing here is extreme. The overround step sits high-ish but inside the churn.

## Depth: there *is* a shift

| pooled median | hist 2026 | live | delta |
|---|---|---|---|
| overround | 0.0688 | 0.0664 | −0.0024 |
| line | 13.5 | 14.5 | +1.0 |
| **books per quoted player** | **4.0** | **5.0** | **+1.0** |

Same roster, **different completeness**: the live ladder gets all five books on a typical
player-line where the historical archive typically had four.

**This matters for exactly one reason.** A de-vigged peer consensus over 5 books is not the same
estimator as one over 4 — the leave-one-out peer set changes size, which changes both its
variance and its bias. M30, M31 and M32 are all peer-consensus constructions. Any of them spliced
across this seam would change definition at the seam while appearing continuous.

## Verdict

Using the live ladder **after** the seam, on its own terms, is unaffected.

What is blocked is treating the two archives as **one continuous series** without carrying the
depth difference — and, because the archives do not overlap, nothing here can rule out a further
shift confounded with the date.
