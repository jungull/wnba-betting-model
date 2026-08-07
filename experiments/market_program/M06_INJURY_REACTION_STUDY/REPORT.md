<!-- COORDINATOR HEADER -- materialized, not authored, by the on-duty coordinator -->
# M06_INJURY_REACTION_STUDY -- REPORT

**Materialized by the coordinator on 2026-08-07.** The harness forbids subagents writing a file
named `REPORT.md`, so the node wrote `M06_REPORT_BODY.md` and the coordinator materializes the
official report from it verbatim. Body source: `M06_REPORT_BODY.md`, sha256 `f453dfbc91c46ecdd321c1b329d0e29afddb704750de1913b03d11234bd5fc14`.
Nothing below this header was edited by the coordinator.

## Scope this node was dispatched under

The coordinator dispatched M06 **scoped to a feasibility verdict ONLY**, per
`COORDINATOR_HANDOFF_2026-08-07` section 9.4: *"Feasibility verdict is a legitimate output; a
reaction claim is not."* No reaction-time estimate, latency figure, or tradability claim was
authorised, and none was produced. **VERDICT: `NOT_YET_FEASIBLE`.** Returning that verdict is the
node succeeding, not failing.

## Coordinator verification (performed on bytes, not accepted on assertion)

- `FINDINGS.json` parses; `feasibility_verdict` = `NOT_YET_FEASIBLE`.
- The headline linkage result was re-read directly from the artifact: of **7** genuine injury
  status transitions, **0** have both before- and after-event price coverage (5 before-only, 2 with
  no matching tracked game or player).
- **Independent cross-check between two agents.** M06 and M10 read the same odds store without
  coordination and their numbers reconcile exactly: total rows 4,526; prop rows 4,196; game-line
  window `2026-08-07T14:03:04Z -> 15:22:05Z`. The one apparent divergence -- M06 reporting 330
  game-line rows against M10's 220 -- was resolved by the coordinator counting the file directly:
  `h2h` 110, `spreads` 110, `totals` 110. M06's 330 is all game lines; M10's 220 is spreads+totals
  only, which is correct for middles because a moneyline has no line to middle. **Both are right at
  different scopes; there is no contradiction.**

## The two caveats that matter

**The 7 transitions are not organic news flow.** All 7 landed inside a single 112-second catch-up
burst, not spread across the 15-minute capture cadence. Even had prices covered them, 7 clustered
events would not support a reaction-time study.

**The verdict is `NOT_YET_FEASIBLE`, deliberately not `UNSUPPORTABLE`.** Unlike M07's structural
batched-timestamp problem -- which no amount of further capture can fix -- this is an accumulation
and overlap gap that continued capture could plausibly close. The report lists five concrete
conditions that would change the verdict. Note also that all 4,526 odds rows still carry
`vendor_ts_semantics=unknown_unverified` with an empty latency note: M26's new instrumentation has
so far been exercised only by other nodes' one-off manual calls, not by the regular scheduler.

**Open item surfaced, not resolved here:** the node flagged a stale README in the PROGRAM worktree
that undercounts the real tape because it references only the frozen, non-growing seed copy of the
injury data rather than the DATA-worktree store the scheduler actually writes to. That is outside
this node's write scope and is carried as a coordinator follow-up.

---

# M06_INJURY_REACTION_STUDY -- REPORT

**Epistemic status (verbatim, per node contract):** PROSPECTIVE EVENT STUDY. Measures how fast
books react to injury news, on evidence that can actually support timing claims. Gated on a
preregistered minimum of usable events; power accrues with the tape, not with patience for weaker
evidence.

**Scope note, restated because it governs everything below:** the coordinator scoped this node to
a **feasibility verdict only**. "Feasibility verdict is a legitimate output; a reaction claim is
not." No reaction-time estimate, latency figure, direction, or tradability claim appears anywhere
in this report or in `FINDINGS.json`. Everything below is a measurement of what tape exists and
whether it overlaps -- never of how fast anyone reacted.

---

## 0. What was read, from which worktree, and what was not touched

- `experiments/player_program/orchestration/prompts/M06_INJURY_REACTION_STUDY.md` (this node's
  contract), `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md`,
  `experiments/player_program/orchestration/GRAPH_POLICY.md` -- all read from the **PROGRAM
  worktree** (`C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program`,
  this session's cwd).
- `experiments/market_program/M26_CAPTURE_MICROSTRUCTURE_REMEDIATION/{REPORT.md,FINDINGS.json}`
  and `experiments/market_program/M07_BOOK_LEAD_LAG/{REPORT.md,FINDINGS.json}` -- **PROGRAM
  worktree**. These establish the capture-layer ceiling this node inherits: M26 fixed the
  game-odds endpoint (previously 200/0-rows-written on every poll) earlier **today**
  (2026-08-07T14:03 UTC, the fix's own live-verification timestamp); M07 measured the pre-fix
  props-only tape and found `vendor_ts_semantics=unknown_unverified` on 100% of rows,
  `vendor_latency_bound=UNBOUNDED`, `clock_skew_bound=UNMEASURED`, and a structural 0-second
  cross-book sync window that cannot be sharpened by more of the same-topology data.
- `experiments/market_program/INJURY_OFFICIAL/live/{README.md,capture_injury_live.py}` --
  **PROGRAM worktree**. This is where the injury-capture *code* lives, and where a **frozen seed**
  (28 docs / 552 snapshot rows, committed alongside the code) sits. It does **not** grow: the
  scheduled task (`injury_live_tick.cmd`, DATA-worktree root) sets
  `INJURY_LIVE_DATA_ROOT=C:\Users\jgallagher\wnba-betting-model\data\injury_official_live` so the
  live 15-minute-cadence writes land only in the DATA worktree, keeping the program worktree
  quiescent for pushes (D018/D044). A naive read of the program-worktree copy alone would
  undercount the real tape by more than 30% (552 vs. 813+ rows, growing) and would miss ~15 hours
  of live capture entirely.
- **Real tape, read directly, no network calls, no vendor credits spent:**
  - `C:/Users/jgallagher/wnba-betting-model/data/injury_official_live/{capture_log,injury_snapshots,status_transitions}.csv`
    -- **DATA worktree**, the actual scheduler-written injury tape.
  - `C:/Users/jgallagher/wnba-betting-model/data/market_snapshots/{snapshots,poll_log,vendor_timing_log}.csv`
    -- **DATA worktree**, the actual scheduler-written odds tape.
  - `C:/Users/jgallagher/wnba-betting-model/injury_live_tick.cmd` -- **DATA worktree root**, the
    scheduled-task launcher, read to confirm where it actually writes (not assumed).
- **Not read:** `experiments/player_program/stage2b/SEALED_RESULTS` (forbidden input, per node
  contract). Nothing under `data/drive_masters/master_odds.csv` (the T2 final-state archive) was
  opened -- this node's mandate is entirely a point-in-time question, and M00 Section 5's
  enumerated uses (U1-U6) contain no timing-relevant use that would even be relevant here, so
  there was no reason to touch it (mirrors M07's own reasoning).
- **No live pull was triggered.** All numbers below come from
  `experiments/market_program/M06_INJURY_REACTION_STUDY/analyze_feasibility.py`, run as
  `python analyze_feasibility.py` from this directory, reading only files already on disk.
  `vendor_timing_log.csv`'s 16 rows were written by M26's and (concurrently) M27's own
  live-verification calls earlier today, not by this node -- this node made zero HTTP requests.

---

## 1. Injury-news tape inventory (DATA worktree, the real scheduler-written store)

Command: `python analyze_feasibility.py` (this directory) -> `feasibility_measurement.json`,
key `injury_tape_data_worktree`.

| Quantity | Value |
|---|---|
| `capture_log.csv` rows (every attempted fetch, incl. failures) | 144 |
| `capture_log.csv` outcome distribution | `NOVEL_BROWSER_CLIENT`: 79, `NETWORK_UNAVAILABLE`: 65 |
| `capture_log.csv` attempted-timestamp range | 2026-08-06T19:41:41Z -> 2026-08-07T15:57:03Z |
| `injury_snapshots.csv` rows | 813 |
| `injury_snapshots.csv` retrieval-timestamp range | **2026-08-07T03:05:56Z -> 2026-08-07T15:57:19Z** |
| Distinct NOVEL capture IDs (i.e., distinct documents that actually changed content) | 79 |
| `status_transitions.csv` rows total | 942 |
| ...of which `status_after == REMOVED_FROM_REPORT` (structural, a player simply not printed this cycle -- **not** injury news) | 913 |
| ...of which a genuine status-to-status transition (`status_before` non-blank, i.e. an actual reported-status change) | **7** |

**Confirms, rather than assumes, the task's stated premise:** just over 45% of all poll attempts
(65/144) are honest `NETWORK_UNAVAILABLE` rows, consistent with the D048 real-headed-Chromium
client needing an interactive desktop session and the scheduled task's own comment about
logged-out cycles. The tape genuinely only starts producing usable snapshot rows on
**2026-08-07**, matching the task's framing that this track "only began witnessing around
2026-08-06/07" -- the capture_log's first attempt is 2026-08-06T19:41Z, but the first **NOVEL**
document (the first one that actually produced snapshot rows) is 2026-08-07T03:05:44Z, roughly
7.5 hours later.

**A caveat about the 7 genuine transitions, measured not assumed:** all seven land within a single
**112-second wall-clock window** (03:06:48Z -> 03:08:40Z on 2026-08-07), each ~10-20 seconds after
the last. This is the signature of a discovery-loop **catching up through a backlog of
already-published documents in quick succession**, not seven independently-arriving pieces of
real-time news 15 minutes apart. The `[t_lower, t_upper]` interval-censoring bounds recorded on
each row are honest about what was directly witnessed (the gap between two consecutive processed
documents), but that gap does not represent the report's real 15-minute publish cadence during
this catch-up burst -- flagged here because a future node building on this tape must not read
these bounds as "reaction happened within 10 seconds of the news."

Contrast, program-worktree seed (frozen, does not grow): `capture_log.csv` 93 rows,
`injury_snapshots.csv` 552 rows, `status_transitions.csv` 30 rows (28 docs, per
`injury_live_tick.cmd`'s own comment). The DATA-worktree tape has grown by 51 additional NOVEL
documents (79 - 28) and 261 additional snapshot rows (813 - 552) since that seed was committed.

---

## 2. Odds tape inventory (DATA worktree, the real scheduler-written store)

Same script, key `odds_tape_data_worktree`.

| Quantity | Value |
|---|---|
| Total rows, `data/market_snapshots/snapshots.csv` | 4,526 |
| Player-prop rows (`player_points`/`rebounds`/`assists`/`threes`) | 4,196 |
| Game-line rows (`h2h`/`spreads`/`totals`) | **330** |
| Overall retrieval-timestamp range | 2026-08-06T18:52:04Z -> 2026-08-07T15:22:05Z (~20.5h) |
| Player-prop retrieval-timestamp range | 2026-08-06T18:52:04Z -> 2026-08-07T15:22:05Z (~20.5h) |
| **Game-line retrieval-timestamp range** | **2026-08-07T14:03:04Z -> 2026-08-07T15:22:05Z (~79 min)** |
| Distinct games in the entire tape | 5 |
| `vendor_ts_semantics` on the 4,526 rows | `unknown_unverified`: 4,526 (100%) |
| `vendor_latency_note` non-empty | 0 of 4,526 |

**The M26 fix is confirmed live in the bytes, not just in M26's own report:** game-line rows exist
at all only from 2026-08-07T14:03:04Z onward -- exactly M26's fix-verification timestamp. Before
that instant, this tape (like M07 measured) is 100% player props. **The game-line odds tape is
therefore, at the moment of this measurement, 79 minutes old.**

**M26's Defect 4 fix (latency/clock-skew instrumentation) exists but has not reached the ordinary
tape.** `vendor_timing_log.csv` has 16 rows, all tagged `game_id` values prefixed
`M26-VERIFY-`/`M27-VERIFY-` -- i.e., written by other nodes' one-off manual verification calls
earlier today, not by the regular scheduled capture loop. Every one of the 4,526 rows in
`snapshots.csv` itself still carries `vendor_ts_semantics=unknown_unverified` and an empty
`vendor_latency_note` -- the amendment-4 fields on the tape that a study would actually consume
remain unbounded for the ordinary poll stream, independent of the event-coverage problem in
Section 3below.

**Per-game poll density, measured directly (not assumed from the ladder design doc):**

| game_id | props rows | game-line rows | poll instants | poll-instant range |
|---|---|---|---|---|
| `58beff9061f1...` (LVA @ IND) | 649 | 0 | 4 | 2026-08-06T18:52Z -> 22:42Z |
| `0c6ed7c2d945...` (LAS @ MIN) | 664 | 0 | 4 | 2026-08-06T20:52Z -> 2026-08-07T00:42Z |
| `2036e6c92c8c...` (TOR @ PDX) | 588 | 0 | 4 | 2026-08-06T21:52Z -> 2026-08-07T01:42Z |
| `0cc93c06f67e...` (ATL @ WAS) | 2,061 | 198 | 21 | 2026-08-06T23:02Z -> 2026-08-07T15:22Z |
| `19f38817b459...` (PHX @ CON, inferred from roster) | 234 | 132 | 4 | 2026-08-07T15:12Z -> 15:22Z |

Four of the five games' props polling **stops hours before the injury tape's snapshot window even
begins** (03:06Z). Only one game (ATL @ WAS) has been polled continuously across the full session
-- it is also the game M26/M27 used for their own live-verification calls, which materially
inflates its poll-instant count above what the ordinary schedule alone would show.

---

## 3. The overlap measurement -- the deliverable this node exists to produce

Command: same script, key `linkage_coverage_check`. For **every one of the 7 genuine injury
status-transitions** (Section 1), checked whether the odds tape carries a player-prop price
snapshot for that exact player+game **both before and after** the event's witnessed `t_upper`
bound. This is a coverage count only -- no price delta, direction, or elapsed time is computed at
any point in this check.

| player | team | transition | matched game in odds tape? | nearest BEFORE price | nearest AFTER price | coverage |
|---|---|---|---|---|---|---|
| Marina Mabrey | Toronto Tempo | Questionable -> Available | yes (TOR@PDX) | 2026-08-07T01:42:03Z | **none** | BEFORE_ONLY |
| Aliyah Boston | Indiana Fever | Probable -> Available | yes (LVA@IND) | 2026-08-06T22:42:04Z | **none** | BEFORE_ONLY |
| Caitlin Clark | Indiana Fever | Probable -> Available | yes (LVA@IND) | 2026-08-06T22:42:04Z | **none** | BEFORE_ONLY |
| Dana Evans | Las Vegas Aces | Questionable -> Available | **no** (not a tracked prop player) | -- | -- | NO_MATCHING_GAME |
| Ariel Atkins | Los Angeles Sparks | Probable -> Available | yes (LAS@MIN) | 2026-08-07T00:42:05Z | **none** | BEFORE_ONLY |
| Bridget Carleton | Portland Fire | Probable -> Available | yes (TOR@PDX) | 2026-08-07T01:42:03Z | **none** | BEFORE_ONLY |
| Teja Oblak | Portland Fire | Doubtful -> Out | **no** (not a tracked prop player) | -- | -- | NO_MATCHING_GAME |

**Result: `n_with_before_and_after_coverage = 0` out of 7.**

The mechanism is visible directly in Section 2's per-game table: the three games these five
matched events touch (LVA@IND, LAS@MIN, TOR@PDX) all stopped being polled between
2026-08-06T22:42Z and 2026-08-07T01:42Z -- **hours before** the injury tape's snapshot window even
opens at 03:06Z. Every one of those events has a "before" price only because props were captured
pregame; none has an "after" price because, whatever the reason (game commence / in-play exclusion
per M00 Section 4.4, or the capture ladder simply moving off a game once it starts), this capture
topology stopped watching those games' prices before the injury news landed in the tape.

The game-line tape (h2h/spreads/totals, 2026-08-07T14:03Z -> 15:22Z) does not rescue this either:
it covers ATL@WAS and PHX@CON, neither of which had a genuine (before/after) injury transition in
this session's tape.

**Raw wall-clock overlap of the two tapes' overall witnessing ranges** (for completeness, distinct
from the event-level coverage check above, which is the actual feasibility question):
- injury snapshots `[03:05:56Z, 15:57:19Z]` intersect props `[18:52:04Z prior day, 15:22:05Z]` =
  **~12h16m of raw overlap**.
- injury snapshots intersect game-lines `[14:03:04Z, 15:22:05Z]` = **~79 min of raw overlap**, and
  zero genuine injury transitions fall inside that 79-minute window.

The raw-range overlap is wide; the **usable-event overlap is zero**. This is the finding: having
two tapes whose date ranges intersect is not the same as having events with the specific
before/after coverage a study needs, and the gap between those two facts is exactly what this
node was asked to measure.

---

## 4. Feasibility verdict

**NOT YET FEASIBLE.**

- `n_usable_linked_events = 0` (before-and-after price coverage), against 7 genuine injury
  status-transitions witnessed in the tape to date, 5 of which matched a tracked game/player at
  all.
- No preregistered minimum-n was reached, was even attempted, or could meaningfully be set yet --
  0 is below any plausible threshold, so the specific minimum-n design question is out of this
  node's scope (feasibility only) and is left to whichever future node runs once the verdict
  changes.
- Even where "before" coverage exists, the amendment-4 fields required on any eventual estimate
  (`vendor_latency_bound`, `clock_skew_bound`) are **UNBOUNDED / effectively unmeasured** on the
  ordinary tape (Section 2) -- a second, independent reason no reaction-time claim could be made
  even if event coverage existed today.
- The game-line tape that M26 fixed today is real and growing (330 rows, 2 games, 79 minutes old
  at measurement time) but has not yet coincided with any injury event.

This is not a structural impossibility of the kind M07 found for cross-book lead-lag (there, the
capture topology itself -- one shared batched timestamp per poll -- made finer resolution
impossible **regardless of how much more tape accumulates**). Here, the blocker is **accumulated
overlap**, which the two capture pipelines can plausibly close over time. Hence `NOT YET FEASIBLE`
rather than `UNSUPPORTABLE`.

### What minimum tape would change the verdict

1. **Odds polling that survives past the injury tape's active window for the same game.** Every
   observed gap is caused by odds capture for a game stopping (near commence, per the in-play
   exclusion structural rule, or simply falling off the ladder) before or during the window when a
   real injury-status change gets witnessed. At minimum: one game where props/game-lines continue
   to be polled through a pregame window that also contains a genuine (non-backfill, single-cycle)
   status transition for a tracked player on that game.
2. **A settled, non-backfill cadence for the injury tape.** The only 7 genuine transitions
   observed so far arrived in a 112-second catch-up burst, not the report's real 15-minute publish
   grid -- a preregistered study needs transitions witnessed under ordinary running conditions, not
   backlog processing, so the `[t_lower, t_upper]` bounds mean what they claim to mean.
3. **Amendment-4 fields actually populated on the ordinary tape**, not only on one-off manual
   verification calls -- M26's `vendor_timing_log.csv` mechanism needs to be wired into the regular
   scheduled poll loop (a capture-layer change, out of this node's scope) before
   `vendor_latency_bound`/`clock_skew_bound` stop being UNBOUNDED/UNMEASURED on the rows a study
   would actually use.
4. **A preregistered minimum-n set before any results are visible** (per this node's own
   acceptance criteria) -- deferred entirely, since 0 usable events makes the question moot for
   now, but a future FEASIBLE verdict must not skip this step.
5. **Enough independent game clusters.** M07 already established, for the cross-book question,
   that game (not comparison-count) is the correct independence unit and that this tape's ~5 game
   clusters are far short of what a generalizable claim needs. The same discipline applies here by
   analogy: even once event-level coverage exists, a handful of overlapping events in one or two
   games would not constitute a powered study.

---

## 5. Could not establish

- **Whether the PHX@CON game (`19f38817b459...`)'s team assignment is exactly right.** Inferred
  from the player-roster overlap between the odds tape's tracked outcomes (Alyssa Thomas, DeWanna
  Bonner, Diamond Miller, Kahleah Copper, Kelsey Plum, Leïla Lacan, Olivia Nelson-Ododa) and the
  injury tape's `PHX@CON` matchup rows, not from a direct game_id-to-matchup join (no such join
  key exists in either tape as captured -- this mirrors M07's own flagged gap between M05's
  linkage-input schema, which expects raw team/commence-time columns, and the live capture
  schema, which stores only a pre-resolved vendor `game_id`). Did not affect the verdict: even
  under the most permissive possible team assignment, no genuine transition maps to this game
  within the odds tape's coverage window for it (15:12Z-15:22Z, after this session's injury tape's
  most recent genuine transition at 03:08:40Z).
- **The true real-world time of the news event behind each of the 7 genuine transitions.** Because
  they were witnessed in a rapid catch-up burst (Section 1), the actual document-publication time
  for each transition could be considerably earlier than its witnessed `t_upper` -- the tape as it
  exists does not let this be pinned down further; `provider_publication_ts_raw`/
  `provider_publication_ts_et` fields exist in the schema per-row but were not cross-checked
  against the PDF content in this node (out of scope: no reaction-time claim is being made, so no
  timestamp precision beyond what Section 1 already reports was needed).
- **Whether additional genuine transitions have landed since this measurement was taken.** The
  scheduled task keeps running; re-running `analyze_feasibility.py` at a later time will pick up
  any growth. A repeat check partway through this session (after the tape had grown further) still
  showed exactly 7 -- stated as a point-in-time measurement, not a permanent count.
- **A numeric vendor-pricing or latency figure for anything** -- out of scope by the node's own
  stop conditions and not attempted.

---

## 6. Contradictions found

1. **The README at `experiments/market_program/INJURY_OFFICIAL/live/README.md`** (PROGRAM
   worktree) states, in its "Run status this session" section, that
   `injury_snapshots.csv, status_transitions.csv, report_coverage.csv, and rejects.csv are
   therefore headers-only as of this session." This is true **only of the program-worktree copy**
   at the time that README was written. It is stale/misleading if read in isolation today without
   the `INJURY_LIVE_DATA_ROOT` redirection context from `injury_live_tick.cmd` -- the real,
   scheduler-written tape in the DATA worktree has 813 snapshot rows and 79 distinct captured
   documents. Not treated as a defect in that node's own work (the README was accurate for its own
   session and explicitly documents the redirection mechanism); flagged here because a future
   reader following only the program-worktree path would draw the wrong conclusion about tape
   size, exactly the trap this node's dispatch instructions warned about.
2. **No numeric contradiction found between M26/M07's reported figures and this node's own
   independent re-derivation of the odds tape** -- M26's live-verification transcript
   (`n_written=256`, `66` game-line rows, `190` props rows for one poll cycle) and M07's tape
   characterization (3,152 rows, 4 games, all-props, as of its own measurement time) are both
   consistent with this node's measurement of the tape's current, larger state (4,526 rows, 5
   games, 330 game-line rows) -- the difference is exactly the additional capture that has landed
   since those nodes ran, not a discrepancy.

---

## 7. Stop conditions

None were tripped requiring a HALT. No money was spent, no wager was placed, no credential was
entered or held beyond what capture code already uses, no scraping/licensing risk was accepted,
and `experiments/player_program/stage2b/SEALED_RESULTS` was never read. No live vendor pull was
triggered by this node -- every number above comes from files already on disk at measurement time.
No reaction-time or timing claim was attempted, so the "report as UNSUPPORTABLE" stop condition
does not apply here (there is no claim to be unsupportable) -- the feasibility verdict itself
(`NOT YET FEASIBLE`) is the deliverable, exactly as the coordinator's scoping note anticipated.
