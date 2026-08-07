# M27_PER_BOOK_POLLING -- REPORT_BODY

**Node:** M27_PER_BOOK_POLLING · **Date:** 2026-08-07
**Machine-readable companion:** `FINDINGS.json` (this directory)

**Epistemic status:** REMEDIATION + BOUNDED PROSPECTIVE MEASUREMENT. Implements the
D052/D053-authorized scoped per-book polling upgrade on the existing capture code (DATA
worktree root) and reports real, measured evidence from a live verification run against the
live vendor API. Asserts no market-opportunity finding -- that is out of scope for this node.

Filename note: per the dispatch instructions this file is named `M27_REPORT_BODY.md`, not
`REPORT.md` (the harness refuses both `REPORT.md` and `REPORT_BODY.md` as write targets for a
subagent) -- same pattern every sibling market-program node has hit and resolved the same way.

---

## 0. What this node does and does not do

M07_BOOK_LEAD_LAG measured a structural defect: every book in a poll shares one
byte-identical `retrieval_ts`, because the vendor bundles every subscribed bookmaker into one
JSON payload per HTTP call -- so the cross-book synchronization window was exactly 0 seconds
**by construction**, and no lead-lag claim could ever be supported regardless of sample size.
M26_CAPTURE_MICROSTRUCTURE_REMEDIATION fixed the code-artifact half (odds and props calls now
get their own real timestamps) and explicitly left the vendor-shape half open, routing the
cost/quota decision to the user rather than self-granting it.

This node implements that routed decision, **bounded**: a declared 3-book subset, a declared
60-minute pre-tip window, a documented kill switch, and real measured evidence -- not an
open-ended "poll every book always" change. Sections 1-2 justify the scope from the tape.
Section 3 is the code change. Section 4 is the test evidence. Section 5 is the live
verification run and the credit-burn measurement/projection, including an important anomaly
this node found but did not cause. Section 6 is the recommendation.

---

## 1. Declared book subset: betrivers, draftkings, fanduel

Command: `python analyze_tape.py` (this directory), reading
`data/market_snapshots/snapshots.csv` (3,651 rows as of this run) directly. Output:
`tape_analysis.json`.

Price-change density per book (same series-key convention M07 adopted --
`(game_id, book, market, outcome, line)`, sub-1-second echo-poll duplicate ticks excluded):

| book | rows | changes |
|---|---|---|
| betrivers | 820 | **265** |
| draftkings | 670 | **204** |
| fanduel | 664 | **174** |
| betonlineag | 689 | 144 |
| williamhill_us | 529 | 76 |
| (6 other book keys) | 6 each | 0 each |

The six other book keys (betmgm, betus, bovada, fanatics, lowvig, mybookieag) are single-poll
artifacts from an unrelated M26 live-verification run -- not ongoing coverage -- and are
excluded from the ranking.

**Declared subset: betrivers, draftkings, fanduel** -- the top 3 by measured change density,
together accounting for 643 of 863 total observed price-change events across all tracked books
(**74.5%**). betonlineag and williamhill_us, the two excluded regularly-polled books, together
account for the remaining 220 (25.5%).

---

## 2. Declared pre-tip window: last 60 minutes before tip

`data/market_snapshots/snapshots.csv` carries no `commence_time` column. Tip times were
back-computed from `market_ladder_scheduler.LADDER_RUNGS`' own (label, hours-before-tip) table
applied to the `poll_ts` and `label` recorded in `poll_log.csv` for each ladder-rung poll,
averaged across every rung observed for a game (`analyze_tape.py`'s
`estimate_tip_times`) -- e.g. a T-2h poll firing at `poll_ts` implies `tip ≈ poll_ts + 2h`. The
implied-tip spread across a game's own observed rungs was 300-301 seconds (5 minutes) for all
3 games with enough rung history to estimate -- consistent with the ladder's own
`LEAD_MINUTES`/`FIRE_GRACE_MINUTES` firing tolerance, not a sign of a bad method. The 4th game
in the tape had no resolvable rung history in time for this estimate and was excluded (157 of
863 change events fall on it and were excluded from the bucketing below, not imputed).

Every price-change event (706 of them, after excluding the 157 above) was tagged with
hours-before-tip using its own `retrieval_ts` and its game's implied tip, then bucketed:

| bucket | width (min) | changes | rate (changes/min) |
|---|---|---|---|
| 2h-4h before tip | 120 | 251 | 2.09 |
| 1h-2h before tip | 60 | 222 | 3.70 (+77% vs. 2h-4h) |
| 0-15m before tip | 15 | 233 | **15.53** (+643% vs. 2h-4h, +320% vs. 1h-2h) |
| all other buckets (30m-1h, 15m-30m, >24h, 8-24h, 4-8h, post-tip) | -- | 0 | -- |

(The zero-count buckets are an artifact of the ladder itself only firing at discrete rungs
T-4h/T-2h/T-60m/T-15m -- every observed change lands in the bucket nearest one of those four
rungs, not evidence those windows are truly silent; only the *relative rate* across the three
populated buckets is used as evidence here.)

The per-minute change rate rises sharply as tip approaches, peaking over 7x the 2h-4h baseline
in the final 15 minutes. **Declared pre-tip window: the last 60 minutes before tip**
(`PER_BOOK_PRE_TIP_WINDOW_MINUTES = 60.0`) -- wide enough to capture the full 1h-2h -> 0-15m
acceleration, and it composes with (does not duplicate) the ladder's own existing T-60m /
T-15m / final_pregame rungs rather than opening a new window outside them.

**Declared interval: 300 seconds (5 minutes)** -- reuses
`market_ladder_scheduler.BURST_LEG_INTERVAL_SECONDS`, an existing constant in this codebase,
rather than inventing a new cadence number.

**Important operational caveat, measured not assumed:** the per-book due-check only runs when
`market_capture_run.py` itself is invoked, and the only current trigger is the
`WNBA_MarketLadder` Windows scheduled task, which ticks every 10 minutes (confirmed via
`Get-ScheduledTask`/`Get-ScheduledTaskInfo` and via `logs/market_ladder/ladder_20260807.log`'s
own 10-minute-spaced entries all day). So the REALISTIC per-book cadence in production is
bounded by that external 10-minute tick -- about 6 cycles per 60-minute window -- not the
theoretical maximum of 12 that the 300-second floor alone would allow under continuous
invocation. Both figures carry through the burn projection in Section 5.

**Declared endpoint scope: props only.** The M07 tape that measured the original defect, and
the density/window analysis above, are entirely player-prop markets. `fetch_odds_snapshot`
(game lines: h2h/spreads/totals) also gained the same optional `bookmakers=` parameter for
parity and future use, but the live per-book scheduling loop in `market_capture_run.py` only
calls the props variant -- this keeps the multiplier's credit cost isolated to one leg.

---

## 3. Code change

Files changed, all in the DATA worktree root (`C:/Users/jgallagher/wnba-betting-model`):

- **`market_capture_config.py`** -- new kill switch `MARKET_PER_BOOK_POLLING_ENABLED` /
  `is_per_book_polling_enabled()` (default disabled), layered on top of the existing
  `MARKET_LADDER_ENABLED` gate, not a replacement for it. New named constants
  `PER_BOOK_DECLARED_BOOKS`, `PER_BOOK_PRE_TIP_WINDOW_MINUTES`,
  `PER_BOOK_POLL_INTERVAL_SECONDS` with their tape-evidence justification inline as docstrings,
  so the scope declaration lives in exactly one place.
- **`market_snapshot_writer.py`** -- `fetch_odds_snapshot` and `fetch_event_props_snapshot`
  both gained an optional `bookmakers: Optional[str]` parameter. When given, the request uses
  `bookmakers=<book>` **instead of** `regions=us` (the vendor documents these as mutually
  exclusive scoping params) -- this is what turns one bundled multi-book call into a genuinely
  independent, separately-witnessed single-book call. Default behavior (`bookmakers=None`) is
  byte-for-byte unchanged from pre-M27.
- **`market_per_book_scheduler.py`** (new) -- `in_pre_tip_window()`, `due_per_book()`, and
  `PerBookCursor` (persisted `_per_book_cursor.json`, same load/save discipline as the existing
  `ChainIndex`/`RosterIndex`). This is a *repeatable, interval-gated* obligation, unlike the
  ladder's *fire-at-most-once-per-rung* model, so it is a separate module rather than a
  extension of `market_ladder_scheduler.due_rungs`.
- **`market_capture_run.py`** -- new `_poll_per_book()`: issues one separate
  `fetch_event_props_snapshot` call per book in `PER_BOOK_DECLARED_BOOKS`, with >=1 second
  politeness spacing between calls (matching the polite-client discipline already used
  elsewhere in this program -- no numeric Odds-API rate ceiling is ledgered in M00 to size
  against more precisely, confirmed by direct search; M26's report flagged the identical gap).
  Each call gets its own `poll_log.csv` row (`obligation_type="per_book"`,
  `label="PER_BOOK:<book>"`) and its own roster namespace
  (`roster_key=f"{game_id}:props:perbook:{book}"`, isolated from the bundled props roster --
  otherwise a single-book call, which by construction only ever sees one book, would falsely
  mark every OTHER book's chains as vanished). Chain history (`prev_snapshot_ref`) uses the
  SAME `ChainIndex` as every other poll path, so a per-book row correctly links into the same
  continuous price history as bundled-poll rows for that `(game, book, market, outcome)`.
  `main()` computes per-book-due games (kill-switch gated) before the `/events` lookup, so a
  per-book-only tick still resolves the vendor event ids it needs.

---

## 4. Test evidence

`tests_M27.py` (this directory), run as `python tests_M27.py` against the real, changed
production modules (imported via `sys.path`, not reimplemented) -- **11 test functions, 34
checks, all PASS**:

```
[PASS] perbook_config_declares_exactly_three_books -- got ['betrivers', 'draftkings', 'fanduel']
[PASS] perbook_config_books_are_the_measured_densest_three
[PASS] perbook_bookmakers_param_sent -- {'bookmakers': 'draftkings', ...}
[PASS] perbook_regions_param_absent_when_bookmakers_given
[PASS] perbook_default_unchanged_regions_still_used -- {'regions': 'us', ...}
[PASS] perbook_default_unchanged_no_bookmakers_param
[PASS] perbook_three_calls_made -- got 3
[PASS] perbook_call_order_matches_declared_books
[PASS] perbook_rows_written / perbook_no_rejected_rows
[PASS] perbook_all_three_declared_books_present
[PASS] perbook_betrivers_single_ts_within_its_own_call
[PASS] perbook_draftkings_single_ts_within_its_own_call
[PASS] perbook_fanduel_single_ts_within_its_own_call
[PASS] perbook_retrieval_ts_pairwise_distinct_across_books -- expected 3 distinct, got 3
[PASS] perbook_retrieval_ts_values_strictly_increasing
[PASS] perbook_poll_log_has_one_row_per_book -- 3 rows
[PASS] perbook_poll_log_labels_identify_book
[PASS] perbook_roster_keys_are_per_book_scoped
[PASS] perbook_roster_does_not_use_bundled_props_key
[PASS] perbook_kill_switch_defaults_disabled
[PASS] perbook_kill_switch_true_enables / perbook_kill_switch_zero_disables
[PASS] perbook_main_still_gated_by_is_enabled_first
[PASS] perbook_ladder_gate_checked_before_per_book_gate
[PASS] scheduler_inside_window_true / before_window_false
[PASS] scheduler_at_tip_excluded -- in-play exclusion: must never fire at or after tip
[PASS] scheduler_after_tip_excluded
[PASS] scheduler_due_first_time_no_prior_poll
[PASS] scheduler_not_due_within_interval / due_after_interval_elapsed
[PASS] scheduler_not_due_outside_window
[PASS] cursor_empty_initially / cursor_reloads_from_disk
[PASS] defect2_multi_book_fixture_has_2plus_books
[PASS] defect2_still_one_ts_across_books_within_one_call
[PASS] m26_anti_faking_test_still_passes_unmodified
```

The load-bearing check is `perbook_retrieval_ts_pairwise_distinct_across_books`: three
declared books, three pairwise-distinct `retrieval_ts` values -- proving the deliverable
(**each book now carries an independent witnessed `retrieval_ts`**), not asserted by fiat.

The last three checks import and re-run `tests_M26.py`'s own
`test_defect2_within_one_payload_books_still_share_one_timestamp_documented` **directly from
its own module** (not reimplemented, so it cannot silently drift from the real test) against
the current, M27-changed production code, and confirm it still fails-safe: within one bundled
HTTP payload (the default `bookmakers=None` path), books still share exactly one
`retrieval_ts`. This is M26's anti-faking test -- it exists specifically to catch a future
change that fabricates per-book timestamps from parse order. This node's change does not
defeat it: independence is only ever produced by genuinely separate HTTP calls
(`bookmakers=<one book>`), never by re-labeling rows parsed out of one shared response.

**No-regression evidence**, full pre-existing suites re-run against the changed production
files:
- `tests_M26.py` (M26_CAPTURE_MICROSTRUCTURE_REMEDIATION) -- **9/9 test functions pass**.
- `experiments/market_program/M03_CAPTURE_UPGRADE/TESTS.py` -- **69 tests, OK (1 skipped**,
  a pre-existing gated live-smoke skip, unrelated to this node**)**.

---

## 5. Real evidence: live verification run

`live_verify_M27.py` (scratchpad, not a repo deliverable -- same discipline as M26's own
`live_verify_defect1.py`) called the REAL production `market_capture_run._poll_per_book`
against the real, live Odds API, using the already-provisioned key, against a real on-slate
game: **Atlanta Dream @ Washington Mystics** (vendor event id
`0cc93c06f67e3eeac12f320fbf0a5d2f`, commence `2026-08-07T23:30:00Z`). The scheduler's
window gate was deliberately bypassed for this direct call -- no real game was inside its
60-minute pre-tip window at test time (this game's tip was ~8.5 hours away) -- matching
exactly how M26's own live verification called `_poll_and_write` directly for the same reason.
Production window/interval gating is separately covered by `tests_M27.py`'s scheduler tests
(Section 4), not by this live call. Full transcript: `live_verification_transcript.txt`.

**Ran 2 cycles** (a "small number of real cycles" per the mandate), each cycle = 3 calls (one
per declared book):

| poll_ts | label | http_status | credits_last | credits_remaining | n_rows_written |
|---|---|---|---|---|---|
| 15:00:49.553704Z | PER_BOOK:betrivers | 200 | 4 | 51925 | 49 |
| 15:00:50.632431Z | PER_BOOK:draftkings | 200 | 4 | 51891 | 36 |
| 15:00:51.842584Z | PER_BOOK:fanduel | 200 | 4 | 51857 | 36 |
| 15:00:54.004054Z | PER_BOOK:betrivers | 200 | 4 | 51792 | 49 |
| 15:00:55.163097Z | PER_BOOK:draftkings | 200 | 4 | 51758 | 36 |
| 15:00:56.377826Z | PER_BOOK:fanduel | 200 | 4 | 51724 | 36 |

All 6 calls HTTP 200, 0 rows rejected, 242 rows written total. **Credits consumed by this
node's own verification: 24** (6 calls x 4 credits, from the self-reported, process-attributable
`credits_last` field on every row).

### 5.1 Cross-book synchronization window -- now a real, non-zero distribution

| | cycle 1 | cycle 2 |
|---|---|---|
| betrivers -> draftkings | 1.078727s | 1.159043s |
| draftkings -> fanduel | 1.210153s | 1.214729s |
| full cycle span (betrivers -> fanduel) | 2.288880s | 2.373772s |

Mean adjacent-pair gap: **1.166s**. Mean full-cycle span: **2.331s**.

This directly closes M07's structural finding ("the cross-book synchronization window in this
tape is exactly 0 seconds, by construction, for every single poll" -- M07 Section 5) for the 3
declared books on the props leg: `snapshots.csv` now shows each declared book with its own
distinct `retrieval_ts` per per-book poll cycle (confirmed directly in the live tape, not just
in a test fixture -- see the "Distinct retrieval_ts values" section of
`live_verification_transcript.txt`).

**Caveat, stated plainly, not smoothed over:** this window is dominated by this
implementation's **own** 1-second politeness spacing between sequential calls, plus real
per-call HTTP latency (~0.06-0.2s, consistent with M26's own `rtt_seconds` measurements). It is
**not yet evidence of independent vendor-side book-update timing**, and does **not** by itself
support any lead-lag or reaction-time claim under M00 Section 6 -- `vendor_latency_bound` and
`clock_skew_bound` for this specific measurement were not separately sourced here, and 2 cycles
on 1 game is nowhere near a powered sample (M07 found even the full historical tape's ~4 game
clusters underpowered for a first-mover ranking). What changed is structural: the capture
topology now **can** produce a non-zero, per-book-independent timestamp distribution at all,
where before it could not by construction. Whether that distribution, accumulated over many
more real polls, eventually supports a lead-lag claim is exactly the kind of follow-on question
M07 described as needing "a capture redesign" for -- this node is that redesign's first bounded
slice, not the finished analysis.

### 5.2 Credit burn: measured, then projected

**Per-cycle cost:** 3 books x 4 credits/call = **12 credits/cycle** (measured: every one of the
6 real calls reported `credits_last=4`, identical to the pre-M27 bundled props call's per-call
cost -- the multiplier vs. the old single bundled call comes purely from call COUNT, a clean
**3x** for this 3-book scope, not the "5-11x" M26 speculated for tracking every book
individually).

**Cycles per game per window:**
- Theoretical max if invoked continuously (60min window / 300s declared floor): **12**
- Realistic, bounded by the existing `WNBA_MarketLadder` 10-minute external tick (Section 2):
  **6**

**Cost per game:** theoretical max = 144 credits; **realistic = 72 credits**.

**Games per week**, from repo evidence (not general knowledge): directly measured from
`data/odds_capture/live_20260807T150003Z.json` -- 2 games on 2026-08-07, 3 on 08-08, 1 on
08-09 (6 games / 3 days = **2.0 games/day**). The existing design doc
(`W1_DRAFTS/CAPTURE_UPGRADE_DESIGN.md`) separately assumes "typical slate 2-4 events"/day and
"4-5 game days/week" for its own cost model. Combining both into a low/mid/high range:
**8 / 14 / 20 games/week**.

**Weekly burn (M27's own incremental addition only):**

| scenario | realistic (72 cr/game) | theoretical max (144 cr/game) |
|---|---|---|
| low (8 games/wk) | 576 | 1,152 |
| mid (14 games/wk) | 1,008 | 2,016 |
| high (20 games/wk) | 1,440 | 2,880 |

**Every scenario stays under the ~15,000-credit stop threshold by a wide margin on a weekly
basis.** Weeks to accumulate 15,000 credits: ~14.9 weeks at realistic-mid, ~5.2 weeks even at
theoretical-max-high. **The "STOP and report instead of running it" clause was not triggered.**

Against the currently remaining 51,724 credits (Section 5.3), even the fastest scenario
(theoretical-max-high, 2,880/week) would take roughly 18 weeks to exhaust the current balance
from M27's own addition alone -- before accounting for the legacy jobs' own modest documented
cost (~750-1,500 credits/month, per the design doc) or the anomaly in Section 5.3.

**Could not establish:** no season-end date or games-remaining figure exists anywhere in
either worktree (confirmed by direct search of `prospective_pair/coverage_audit.py`,
`data/masters/master_team.csv`, and every "schedule"-named file/script -- all are script
names, never schedule *data*; `M07_BOOK_LEAD_LAG/REPORT.md` Section 9 independently flagged
the identical gap). This node cannot convert "weeks to 15,000 credits" into "credits to
consume before the season ends."

### 5.3 An anomaly this node found but did not cause

The authorization's 63,657-credit baseline was read at `2026-08-07T14:03:04.923875Z` (the last
`poll_log.csv` row before this node made any change). This node's first real call landed at
`2026-08-07T15:00:49Z`, 57 minutes later, and the `credits_remaining` immediately before that
call was **51,929** -- a drop of **11,728 credits** in 57 minutes, during which **this node's
own code made zero calls** (it did not exist/run yet).

Ruled out as the source, by direct measurement:
1. **This node's own code** -- confirmed; `_poll_per_book` did not exist until this session,
   and did not run until 15:00:49Z.
2. **The `WNBA_MarketLadder` scheduled task** -- confirmed via its own log
   (`logs/market_ladder/ladder_20260807.log`): every 10-minute tick across the ENTIRE
   14:00-15:02 window logged `polls=0 rows_written=0` (the ladder found nothing "due" all
   morning). Zero ladder-driven consumption in this window.
3. **The legacy `WNBA_OddsCapture`** (documented 3 credits/run) **and `WNBA_PropsCapture_1-4`**
   (documented 8-16 credits/snapshot) tasks -- both far too cheap, even summed across every
   scheduled firing possible in a 57-minute window, to explain an 11,728-credit gap.

A second, finer-grained instance of the same pattern showed up **inside this node's own two
verification cycles**: `credits_remaining` fell by 201 credits across the ~7-second span the
two cycles took, of which only 24 credits are this node's own calls -- **177 credits of
concurrent, non-self-initiated consumption inside a single 7-second window**.

Source unattributed. This node has no visibility into other sessions or processes sharing the
same `ODDS_API_KEY` -- most likely explanation is concurrent activity from another node/session
in this multi-agent graph environment, which is outside this node's write scope to
investigate further. **This is flagged as a materially more urgent risk to the total remaining
quota than anything M27 itself adds** -- see the recommendation below.

---

## 6. Recommendation

**Implement -- done, kill switch OFF by default.** `MARKET_PER_BOOK_POLLING_ENABLED` defaults
to disabled; the live scheduled task confirms the new code path is a correct no-op in
production right now (`logs/market_ladder/ladder_20260807.log`'s last line,
`per_book_games_polled=0 per_book_calls=0`, from the tick immediately after this node's code
went live).

**Do NOT flip the switch to a standing always-on schedule change yet.** Two separable reasons:

1. **M27's own incremental burn is small and comfortably bounded** -- 72-144 credits/game,
   every weekly-burn scenario measured stays far under the 15,000-credit stop threshold. This
   part is a clean go on its own merits.
2. **The unattributed ambient-consumption anomaly (Section 5.3) is a materially larger and
   more urgent risk to the total remaining quota than M27 adds**, and this node cannot resolve
   it. Turning on an additional capture layer on top of an unexplained ~11,728-credit/hour (or
   burstier) drain, without first understanding that drain, risks exhausting the remaining
   quota for reasons entirely unrelated to this node's own footprint.

**Recommended next step:** identify the ambient consumer first (most likely another concurrent
session/node sharing this API key). Then run `MARKET_PER_BOOK_POLLING_ENABLED=1` as a
**further-bounded pilot** -- a handful of real game nights, not a standing change -- to confirm
production burn matches the 72-144 credits/game projection under real, continuous scheduling
(rather than this node's direct-call verification), before treating it as permanent.

---

## 7. Could not establish

Reproduced from `FINDINGS.json.could_not_establish`:

1. Season-end date or games-remaining count for the current WNBA season.
2. Root cause of the observed ambient credit consumption (Section 5.3).
3. Whether the measured ~1.17s mean adjacent-book gap reflects real vendor-side timing versus
   being purely an artifact of this implementation's own 1-second politeness spacing.
4. A statistically meaningful cross-book lead-lag estimate (2 cycles on 1 game is far short of
   powered).
5. Real, measured per-call credit cost for the game-odds leg under `bookmakers=` scoping (this
   node's live rollout was scoped to props only; the odds-leg code path exists and is
   unit-tested against fakes, not exercised live).
