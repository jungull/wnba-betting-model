# M07_BOOK_LEAD_LAG — REPORT

**Materialized by the coordinator** from the node agent's REPORT_BODY.md (harness rule). Coordinator
note: the agent's remark that "no M03 output exists" reflects reading the wrong worktree — M03's
outputs are committed in the program worktree; the substantive findings below are unaffected and
were independently confirmed (all five books share one byte-identical retrieval_ts per poll).

---
# M07_BOOK_LEAD_LAG â€” Which book moves first: lead-lag measurement across synchronized captures

**Node:** M07_BOOK_LEAD_LAG Â· **Date:** 2026-08-07
**Machine-readable companion:** `LEAD_LAG.json` (byte-identical copy at `FINDINGS.json` â€” see
Section 0 below for why two files)

**Epistemic status (verbatim, as required):** PROSPECTIVE MEASUREMENT. Lead-lag ordering
between books is claimable only from synchronized multi-book capture; ordering below the
capture cadence or clock-skew bound is unknowable and must be reported as such.

---

## Section 0. A filename contradiction, reported rather than silently resolved

The generated node contract (`experiments/player_program/orchestration/prompts/M07_BOOK_LEAD_LAG.md`)
requires outputs named `REPORT.md` and `FINDINGS.json`. The orchestrator instruction that
spawned this node explicitly said: "Do NOT write any file named REPORT.md -- write
REPORT_BODY.md." These two authorities disagree on the report's filename. Per standing rule 1
("never silently reconcile a contradiction -- report it"), I am flagging this rather than
picking one silently: I followed the direct spawning instruction (no `REPORT.md` was written;
this file, `REPORT_BODY.md`, carries the full required content) and additionally wrote
`FINDINGS.json` verbatim-identical to `LEAD_LAG.json` so the contract's automated validation
hook (`python -c "import json;json.load(open('...FINDINGS.json'))")`) still passes. The
verifier should treat `REPORT_BODY.md` as the contract's `REPORT.md` deliverable.

---

## Section 1. What was read, and what was deliberately not touched

- **Contract read:** `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md`
  and `TAXONOMY.json` -- the frozen evidence ladder, the T0/T1/T2 tier discipline, the D023
  amendment-4 timestamp-uncertainty mandatory fields (Section 6), and the bounded final-state-archive
  use enumeration (Section 5).
- **M03_CAPTURE_UPGRADE:** no node output exists yet -- `experiments/market_program/` has no
  `M03_CAPTURE_UPGRADE/` directory. Only the pre-node design draft
  `experiments/market_program/W1_DRAFTS/CAPTURE_UPGRADE_DESIGN.md` exists, which documents a
  target per-game ladder `T-24h T-8h T-4h T-2h T-60m T-30m T-15m final-pregame`. This is cited
  for corroboration only (Section 3 below), not as an authoritative record of what the live tape
  actually did -- that is measured directly from the tape.
- **M05_EVENT_MARKET_LINKAGE:** read `linkage.py`, `DESIGN_BASELINE.md`, `REPORT.md` for the
  frozen series-key convention (Section 2 below).
- **Live tape (the only data source used for any timing statement):**
  `data/market_snapshots/snapshots.csv`, 3,152 rows, read directly with Python's `csv` module.
- **Not read, per the forbidden-inputs / never-read list:** anything under
  `experiments/player_program/stage2b/SEALED_RESULTS` or `stage3_score/SEALED_RESULTS`.
- **Not used for any timing claim:** the T2 final-state archive
  (`data/drive_masters/master_odds.csv`). It was not opened. Per M00 Section 5, C.2, the archive can
  never support a lead-lag claim, and this node's whole mandate is a lead-lag question, so
  there is no M00-enumerated use (U1-U6) under which touching it would even be relevant here.

All figures below were produced by
`experiments/market_program/M07_BOOK_LEAD_LAG/analyze.py`, run as `python analyze.py` from
that directory, writing `LEAD_LAG.json` (and its byte-identical copy `FINDINGS.json`). A
handful of throwaway exploratory scripts were used first to establish facts about the schema
(the alt-line collision, the echo-poll zero-information check, the byte-identical cross-book
retrieval_ts) before committing to the analysis design; those one-off scripts were not kept,
but every fact they established is re-derived and asserted directly inside `analyze.py` itself
(`key_collisions`, `echo_same`/`echo_diff`, `books_per_poll`/`n_polls_with_all_books_present`
in `LEAD_LAG.json`) so every number below is reproducible from the one retained script.

---

## Section 2. Series identity: adopting, not re-deriving, the M05 convention -- with one flagged deviation

M05's `DESIGN_BASELINE.md` (Section 3, DB-1) freezes the series key as
`(game_id, bookmaker, market, outcome)` with `line` carried as **state**, not key, for
game-level markets (h2h/spreads/totals) -- explicitly noting "the config flag allows per-line
keying for alternate-line props designs later."

`data/market_snapshots/snapshots.csv` is entirely player-prop markets
(`player_points`, `player_rebounds`, `player_assists`, `player_threes`). Running
`(game_id, book, market, outcome)` without `line` produces **160 collided keys**: the same
`(game_id, book, market, outcome, retrieval_ts)` tuple appears twice with different `line` and
`price_over` values but the **same `snapshot_id` and `payload_hash`** -- e.g.
`(58beff90..., betrivers, player_points, "A'ja Wilson", 2026-08-06T18:52:04.642477Z)` appears
with `line=28.5/price_over=110`, `line=26.5/price_over=-130`, and `line=27.5/price_over=-108` --
three simultaneously-offered alternate lines for the same player, not three sequential
reprices. This is the M05-anticipated alternate-line case, so I used
`(game_id, book, market, outcome, line)` -- the DB-1 per-line variant -- as the series key. With
`line` included: **0 key collisions across all 3,152 rows and 704 distinct series** (verified:
`n_key_collisions_after_including_line: 0` in `LEAD_LAG.json`).

**Flagged limitation (preserved, not resolved):** the tape carries no field distinguishing a
book's "main" line from an "alt" line. If a book's main line genuinely moves (e.g. 22.5->23.5)
while its old value happens to coexist briefly as an alt line elsewhere, keying on `line`
would record that as one series ending and a new one starting rather than a `LINE_MOVE` event
on a single continuing series. I did not attempt to resolve this ambiguity by inference -- per
standing rule 7, it is listed in `could_not_establish` rather than papered over.

`game_id` values in the tape are already-resolved identifiers (not raw team names +
commence_time), so M05's `linkage.py` functions (`ERMap.resolve_game`, `build_quote_series`,
which require `home_team`/`away_team`/`commence_time` columns) could not be invoked directly
against this schema -- the schemas don't line up (M05 expects raw broadcast rows; this capture
table stores pre-resolved `game_id`). I used the existing `game_id`/`book` fields as-is rather
than re-deriving identity by any fuzzy or ad hoc method, which satisfies the acceptance
criterion's intent ("never re-derived ad hoc") even though the literal M05 code path wasn't
callable on this table's shape. This mismatch between M03's live-capture schema and M05's
linkage-input schema is itself worth surfacing to the coordinator as a reconciliation gap
between the two nodes.

---

## Section 3. Tape characterization

Command: `python analyze.py` (source in this directory), reading
`data/market_snapshots/snapshots.csv` directly.

| Quantity | Value |
|---|---|
| Rows | 3,152 |
| Distinct games | 4 |
| Distinct books | 5 -- `betonlineag`, `betrivers`, `draftkings`, `fanduel`, `williamhill_us` |
| Distinct markets | 4 -- `player_points`, `player_rebounds`, `player_assists`, `player_threes` |
| Distinct (market, outcome/player) pairs | 152 |
| `vendor_ts_semantics` | `unknown_unverified` on **all 3,152 rows** (0 rows carry a trusted vendor timestamp semantic) |
| `market_status` | `active` on all 3,152 rows (no suspensions/reopenings observed) |
| Retrieval window | 2026-08-06T18:52:04.642477Z -> 2026-08-07T01:42:03.885243Z (6h50m) |
| Distinct global poll instants (batch retrieval timestamps) | 21 |
| Series (game, book, market, outcome, line) | 704 |
| Poll instants where all 5 books present | 21 of 21 (100%) |

Every row's `vendor_ts_semantics` is `unknown_unverified` -- per M00 Section 6.3's own default rule
("defaulting to `unknown_unverified` until vendor documentation or support confirms which")
and Section 4.3's tier discipline, `vendor_ts` on this tape cannot support any timing statement at
all. Every timing figure in this report is built from `retrieval_ts` (our own witnessed
capture clock) only, never `vendor_ts`.

`poll_interval_at_capture` takes exactly 5 distinct values across the tape: 900s (15 min, 491
rows), 3,600s (1h, 486 rows), 7,200s (2h, 483 rows), 14,400s (4h, 441 rows), 86,400s (24h,
1,251 rows). These line up with rungs named in the pre-node design draft
`W1_DRAFTS/CAPTURE_UPGRADE_DESIGN.md` (Section b): `T-15m`->900s, `T-60m`->3,600s, `T-2h`->7,200s,
`T-4h`->14,400s, `T-24h`->86,400s. This is corroborating context only (the draft is not a node
output and was not treated as evidence of anything) -- the actual cadence used below is
measured directly from `retrieval_ts` gaps, not from this field.

---

## Section 4. Capture cadence -- the resolution floor's dominant term

For every series (704 total), consecutive rows were sorted by `retrieval_ts` and the gap
between each consecutive pair computed. This is mandate item 1: "distribution of gaps between
consecutive retrievals of the same game/market/book" (extended to game/market/book/**line**
per Section 2).

**Raw consecutive-gap distribution (all 2,448 consecutive pairs across all series), seconds:**

| min | p10 | p25 | median | p75 | p90 | max | mean |
|---|---|---|---|---|---|---|---|
| 0.24 | 0.25 | 599.9 | 2999.7 | 3602.3 | 7201.3 | 13,799.7 | 2,981.1 |

The bottom decile sits at a fraction of a second. Investigating this: 399 consecutive pairs
across all series have a gap under 1 second (`cadence.echo_poll_pairs_sub_1s_gap` in
`LEAD_LAG.json`). Checking every one of them, **100% show identical `price_over`/`price_under`
state** (`same_state: 399, different_state: 0`) -- these are
back-to-back duplicate poll ticks carrying zero new information, not sub-second reprices. I
also verified this is not an artifact of an insufficiently specific series key (Section 2): with
`line` correctly included, 0 of the sub-1s pairs show a state change.

**De-duplicated cadence (collapsing consecutive retrievals under 1s into one poll instant
first), seconds -- this is the honest "time between polls that could possibly reveal a
change":**

| n | min | p10 | p25 | median | p75 | p90 | max | mean |
|---|---|---|---|---|---|---|---|---|
| 2,049 | 599.5 | 599.9 | 601.8 | 3,000.3 | 6,000.2 | 7,201.3 | 13,799.7 | 3,561.6 |

The finest cadence any series in this tape ever achieved is **~600 seconds (10 minutes)**; the
median de-duplicated gap is **~3,000 seconds (50 minutes)**. This 600s floor, not the sub-1s
duplicate-poll noise, is the real per-series polling resolution.

---

## Section 5. Cross-book synchronization -- a structural finding, not a chosen tolerance

Mandate item 1 asks: how many (game, market) series have >=2 books captured within a tight
synchronization window, and to justify that window from the measured cadence.

Direct check (`analyze.py`'s `books_per_poll` computation): for every one of the 4 games, every
distinct `retrieval_ts` string maps to **exactly 5 distinct books** -- i.e., within one poll
cycle for a game, all 5 books' rows for all 4 markets share **one byte-identical `retrieval_ts`
string**, down to the microsecond. This holds for all 21 global poll instants
(`tape_characterization.n_polls_with_all_books_present: 21` of 21 in `LEAD_LAG.json`).

This is not "a tight window I chose to declare synchronized" -- it is the literal, un-negotiable
fact of how this capture batches its writes: one shared timestamp is stamped across the whole
multi-book payload per poll. So the **cross-book synchronization window in this tape is exactly
0 seconds**, by construction, for every single poll.

Of the 238 distinct (game, market, outcome, line) series-families, **152 (64%)** have at least
one poll instant where >=2 books are present (`n_series_families_with_any_synchronized_ge2_book_poll: 152`
of `n_series_families_game_market_outcome_line: 238` in `LEAD_LAG.json`). The remaining 86
families never had >=2 books simultaneously offering that exact line (a book stopped quoting it,
or only ever offered it once).

**This 0-second window is worse for lead-lag than it sounds, not better.** A 0-second
cross-book gap would be ideal if it reflected genuinely independent, near-simultaneous
per-book polling. Here it means the opposite: the capture design fetches all books in one
shared batch write, so there is **no observed timestamp variance across books to exploit at
all** -- we cannot ask "did book A's row get written a few hundred milliseconds before book B's"
because both share the identical string. Any two books whose price changed between the same
pair of consecutive polls are indistinguishable in order, full stop, regardless of sample size.

---

## Section 6. Price changes -- the events lead-lag needs

Mandate item 1: "the total number of observable price CHANGES (not rows)." A change is any row
in a series (Section 2 key) whose `(price_over, price_under)` differs from the immediately preceding
row of the same series (sub-1s echo-poll pairs excluded -- verified zero-information, Section 4).

**Total price changes across the entire tape: 747**, out of 3,152 rows / 704 series.

Per book: `betrivers` 232, `draftkings` 180, `fanduel` 152, `betonlineag` 121,
`williamhill_us` 62. Per game: 275 / 242 / 189 / 41 (the fourth game, `0cc93c06...`, has the
densest poll schedule -- 9 instants -- but the fewest changes; it also has the shortest
elapsed window before the observed tape cutoff).

Of these 747 changes, **550 (74%) fall inside a "co-occurring" group** -- i.e., >=2 books changed
price for the same (game, market, outcome, line) family in the same poll-to-poll interval
(211 such groups). Per Section 5, every one of these 550 changes shares an identical `retrieval_ts`
with the other book(s) in its group, so **none of the 211 co-occurring groups can be ordered**
-- `INDISTINGUISHABLE_AT_GRID` for all of them. This is reported directly in
`lead_lag_attempt.method_1_within_poll_ordering` in `LEAD_LAG.json`.

---

## Section 7. Lead-lag estimate attempted, per mandate item 2 -- result: no sub-poll ordering exists; a coarse poll-granularity ordering does, but fails the amendment-4 admissibility test

Two things were tried, both against the actual change events from Section 6, matched on
`(game_id, market, outcome, line)`:

**Method 1 -- within-poll ordering.** Already covered: 211 groups, 550 changes, 0 orderable.
`INDISTINGUISHABLE_AT_GRID` for every pair, by construction (Section 5).

**Method 2 -- cross-poll first-mover counts.** For a matched family, if book A's change
interval `(t_prev, t_seen]` ends at or before book B's change interval begins, that is a weak,
poll-granularity-only ordering claim ("A's new price was witnessed by an earlier poll than B's"
-- never a sub-poll reaction time). Raw pairwise cross-product of every A-change x B-change
satisfying this: 886 comparisons. This number **overstates independent information** -- when a
book changes several times across the tape, the cross-product multiplies restatements of the
same underlying ordering. Deduplicating to distinct `(family, leader, follower)` relationships
gives an effective count of **553** (`lead_lag_attempt.method_2_cross_poll_first_mover_counts`
in `LEAD_LAG.json`; raw vs. effective both reported there for auditability).

**Why this cannot become a lead-lag claim under this contract, regardless of the count:**
D023 amendment 4 (Section 6.1 of the M00 contract) requires every reaction-time claim to carry a
`vendor_latency_bound` and a `clock_skew_bound`, both numeric. On this tape: `vendor_ts_semantics`
is `unknown_unverified` for all 3,152 rows (no sourced per-vendor latency bound exists to
configure), and no clock-skew measurement was recorded for this capture run
(`clock_skew_bound: UNMEASURED`). Per M05's own `linkage.py` (`widen_interval`,
`measurement_grid`), an unmeasured clock skew makes the measurement grid `UNBOUNDED` and the
claim `UNSUPPORTABLE` by construction -- I did not need to invent this rule; it is already coded
in the frozen M05 module and directly reused here as the correctness check. **Verdict: any
lead-lag or reaction-time claim from this tape is UNSUPPORTABLE**, stated plainly rather than
worked around (per this node's stop condition #2).

The 553 effective coarse orderings are reported in `LEAD_LAG.json` as a descriptive count only,
explicitly not as a lead-lag or reaction-time finding, and explicitly not attributed a
per-book "fastest book" ranking in this report -- presenting one would misuse the count as
exactly the kind of unsupportable reaction-time statement the contract prohibits.

---

## Section 8. Resolution floor, stated plainly (mandate item 2's mandatory disclosure)

```
cross_book_sync_window_s   = 0        (structural: one shared batch retrieval_ts per poll)
poll_to_poll_cadence_s     = 600 s finest observed, ~3,000 s (50 min) median (de-duplicated)
vendor_latency_bound       = UNBOUNDED (all rows unknown_unverified; no sourced bound configured)
clock_skew_bound           = UNMEASURED (no clock-skew measurement recorded for this run)
```

No lead-lag or reaction-time claim on this tape can be sharper than the poll-to-poll cadence
(>=600s / 10 minutes at best, ~50 minutes typically), and even at that coarse grain the claim is
formally `UNSUPPORTABLE` under amendment 4 because both the vendor-latency and clock-skew terms
are missing entirely, not just wide. **More data does not fix this.** Accumulating additional
polls under the *current* batched-single-timestamp capture topology can only raise confidence
in a poll-granularity ranking; it can never produce a sub-poll-interval reaction time, because
there is no per-book timestamp variance in the design to sharpen. Finer resolution requires a
capture redesign -- independent/staggered per-book polling with a measured clock-skew bound --
which is M03_CAPTURE_UPGRADE's scope, not something this node can manufacture from more of the
same tape.

---

## Section 9. Power / feasibility verdict

Mandate item 3: what sample would be needed for a credible lead-lag claim, and how long the
current ladder would take to accumulate it.

**Two different bottlenecks, not one:**

1. **Comparison volume** (if the amendment-4 terms were eventually resolved by a capture
   redesign): the tape produced 553 effective cross-poll orderings across 10 book pairs in
   6h50m -- a raw rate of ~81 effective orderings/hour. A rough sign-test target of 30 orderable
   comparisons per book pair (300 total across 10 pairs) would be reached at the observed rate
   in **~3.7 hours** of comparable capture (`power_feasibility.estimated_capture_hours_to_reach_target_at_observed_rate`
   in `LEAD_LAG.json`). This is an order-of-magnitude rate extrapolation from one short window,
   not a calibrated power analysis, and is explicitly caveated as such in the JSON.

2. **Independent clusters (the real constraint).** The correct independence unit for any claim
   that generalizes beyond this tape is the **game**, not the book-pair-comparison -- orderings
   drawn from the same game share capture-cycle timing and news environment and are correlated,
   not independent draws (this mirrors the possession-lane's own game-clustering discipline
   cited in the contract's "Scientific state" section, applied here by analogy since no
   market-lane clustering rule is yet frozen). **This tape has exactly 4 game clusters.** No
   volume of within-game comparisons substitutes for more games. A credible claim needs on the
   order of dozens of independently-captured games with dense, ideally staggered, per-book
   polling -- this tape is far short of that regardless of how fast comparison volume
   accumulates. How long that takes in wall-clock time depends on the WNBA schedule's game
   density, which this node did not have data to quantify (no schedule file was read; stated
   here as a gap, not estimated).

**Combined verdict:** even setting aside cluster count, no amount of additional capture under
the *current* topology produces an admissible reaction-time claim (Section 8) -- that requires the
capture redesign. Once redesigned, comparison-volume accumulates fast (hours), but a
generalizable claim additionally needs dozens of game-clusters, which is a multi-week-to-season
question tied to the schedule, not an hours question.

---

## Section 10. Could not establish (preserved, not papered over)

Reproduced from `LEAD_LAG.json.could_not_establish`:

1. **Sub-poll-interval book reaction time** (which book's price moved first, in seconds) --
   capture topology stamps one shared `retrieval_ts` per poll across all books; zero measured
   cross-book timestamp variance exists to order same-poll changes (Section 5).
2. **Any amendment-4-compliant reaction-time claim** -- `vendor_ts_semantics` is
   `unknown_unverified` for all rows and no clock-skew measurement exists for this capture run;
   both mandatory terms are missing, not merely wide (Section 7, Section 8).
3. **A statistically powered first-mover ranking of the 5 books** -- only 4 independent game
   clusters exist in the tape (Section 9); no amount of within-game comparison volume substitutes.
4. **Whether an observed alt-line price difference is a true line move of one continuing series
   or two coexisting alternate lines** -- the tape carries no field distinguishing "main" from
   "alt" lines (Section 2).

---

## Section 11. Contradictions and gaps found between documents/artifacts

1. **Section 0 above** -- `REPORT.md` vs `REPORT_BODY.md` filename conflict between the node contract
   and the spawning instruction.
2. **M05 linkage-input schema vs. the live capture schema** (Section 2) -- `linkage.py`'s
   `build_quote_series` expects raw `home_team`/`away_team`/`commence_time` columns;
   `data/market_snapshots/snapshots.csv` stores a pre-resolved `game_id` and has no
   `commence_time` column at all. The two nodes' I/O contracts don't compose without an
   adapter that doesn't yet exist. Not a Severity A issue on its own (I worked around it by
   using `game_id` as-is, not by re-deriving identity), but worth the coordinator's attention
   before any node tries to literally invoke `link()` against this table.
3. **M03_CAPTURE_UPGRADE has not produced a node output yet** -- no
   `experiments/market_program/M03_CAPTURE_UPGRADE/` directory exists; only the pre-node
   design draft in `W1_DRAFTS/`. This node's mandate assumes M03's schema and cadence
   documentation are readable; in practice only the draft and the live tape itself were
   available, and the tape was the authority used throughout (per standing rule 6, measure
   the actual bytes, don't cite an unstarted node's output as if it were frozen).

No stop condition beyond the two already discussed (Section 0 filename conflict, Section 7 UNSUPPORTABLE
verdict) was tripped. No spend, wager, credential, or licensing-risk situation arose. The T2
archive was never read.

---

## Section 12. Summary

- **Tape:** 3,152 rows / 4 games / 5 books / 4 player-prop markets / 704 series (line included
  in series identity -- Section 2), all `vendor_ts_semantics=unknown_unverified`.
- **Synchronized-pair count:** 152 of 238 (game, market, outcome, line) families have >=2 books
  present at a shared poll instant; the cross-book window is exactly 0s by construction -- every
  poll batches all 5 books under one timestamp.
- **Changes:** 747 total; 550 (74%) fall inside 211 co-occurring cross-book groups, all
  `INDISTINGUISHABLE_AT_GRID`.
- **Estimate possible?** No admissible lead-lag or reaction-time estimate. A coarse,
  poll-granularity cross-poll ordering exists (553 effective relationships) but is
  `UNSUPPORTABLE` under D023 amendment 4 because both `vendor_latency_bound` and
  `clock_skew_bound` are missing (not merely wide) on this tape, and is reported descriptively
  only, never as a lead-lag finding.
- **Resolution floor:** ~600s (10 min) finest, ~3,000s (50 min) median poll-to-poll cadence;
  0s cross-book sync window that provides no ordering information; both latency terms absent.
- **Feasibility verdict:** comparison volume would accumulate in hours once the capture
  topology supports independent per-book timestamps (M03 scope) -- but the binding constraint
  is game-cluster count (4 in this tape; dozens needed), which is a schedule-bound, multi-week
  question this node could not quantify further without schedule data it did not read.
