> Materialized by the agent's returned text (harness forbids a file literally named
> REPORT.md; per dispatch instructions this is M10_REPORT_BODY.md, the coordinator
> materializes REPORT.md from it). `python TESTS.py` -> 95/95 checks pass.

# M10_MIDDLES -- report

**Epistemic status (verbatim, per node contract):** SCANNING INFRASTRUCTURE. Middles
are probabilistic, not risk-free: detection uses the M00 taxonomy's definition and the
EV arithmetic must model push/no-push semantics per book rule set, never a generic
template.

---

## 0. Worktree map, verified not assumed

Per the coordinator's explicit warning about a recurring failure (agents concluding an
upstream contract "does not exist" because they searched the OTHER worktree,
`C:\Users\jgallagher\wnba-betting-model`, branch `data-refresh-2026`):

- This node's task prompt, `M00_MARKET_PROGRAM_CONTRACT.md`, `TAXONOMY.json`, and its
  upstream dependency `M09_TRUE_ARB_SCANNER` (`arb_scanner.py`, `fixtures.py`,
  `TESTS.py`, `coarse_tape_demo.py`, `ACTIVATION_CHECKLIST.md`, `REPORT.md`) all exist
  and were read in full from **this** worktree
  (`experiments/market_program/M09_TRUE_ARB_SCANNER/` and
  `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/`), not the other one.
- The real capture tape this node scans, `data/market_snapshots/snapshots.csv`, does
  **not** exist under `experiments/` in this worktree -- it is a real data file, and it
  lives at the DATA-worktree root `C:/Users/jgallagher/wnba-betting-model/data/
  market_snapshots/snapshots.csv`. This is the SAME location and the SAME root
  convention `M09_TRUE_ARB_SCANNER/coarse_tape_demo.py` already reads from (its own
  `DEFAULT_ROOT = "C:/Users/jgallagher/wnba-betting-model"`), and the same location
  M26/M27's own reports (read in full below) describe as "the DATA worktree root" where
  the live capture code and files actually run. Read-only, confirmed by directly
  `Test-Path`-ing the file before use (1,562,197 bytes at read time) and never writing
  to it or anywhere else outside this node's declared write scope,
  `experiments/market_program/M10_MIDDLES/`.
- I did **not** read or use `experiments/player_program/stage2b/SEALED_RESULTS` (the
  forbidden input) at any point.

---

## 1. What was built

- `middle_scanner.py` -- the engine. Implements `TAXONOMY.json`'s
  `MIDDLES_AND_DISLOCATIONS` class (`MARKET_PROGRAM_CONTRACT.md` section 1.2) for the
  MIDDLES half of that class (two legs on the same market family, different lines).
  Imports M09's stateless timestamp/simultaneity primitives (`parse_ts`, `fmt_ts`,
  `PollLog`, `simultaneity_window`, `canonical_json`, `sha256_hex`,
  `american_to_decimal`, `AppendOnlyFlagLog`) directly from `arb_scanner.py`
  (read-only; M10 never writes to `M09_TRUE_ARB_SCANNER/` and never mutates
  `arb_scanner`'s module-level venue tables) per the dispatch's explicit "reuse rather
  than reinvent" instruction. Defines its own, independent push/void-rule table
  (`PUSH_VOID_RULES`), fee table (`FEE_MODEL`), gap-geometry arithmetic
  (`gap_geometry`, `enumerate_gap_worlds[_with_dnp]`), settlement evaluator
  (`evaluate_middle_settlement`), and EV function (`expected_value`) -- the parts that
  are genuinely this node's own business logic, not M09's.
- `fixtures.py` -- 10 synthetic ground-truth cases (year-2030 timestamps, fictional
  venues, no real bytes), covering: a clean half-point middle, a mirror-line non-middle,
  an inverted-line non-middle, a push-at-leg-A world under both a nonstandard
  (counts-as-win) and standard (void-return) venue rule, a push-at-leg-B totals world, a
  both-boundaries-integer 5-world case, a DNP-risk prop middle with both venues
  verified, the same geometry with one venue unverified (`SETTLEMENT_UNSUPPORTED`), and
  a half-point/half-point gap on an unverified venue (`SETTLEMENT_UNSUPPORTED` via the
  fee-row-required-unconditionally path).
- `TESTS.py` -- 95 checks, all passing (`python TESTS.py` exits 0; prints a
  `{"n_pass": 95, "n_fail": 0, "n_total": 95}` summary and exits 1 on any failure).
- `coarse_tape_demo.py` + `COARSE_TAPE_DEMO_RESULTS.json` -- a labeled, non-authoritative
  replay over the real capture tape (Section 4 below).

## 2. Acceptance criterion 1 -- middles detected per the M00 taxonomy, distinct from arbitrage

**Definition implemented, verbatim from `TAXONOMY.json`:** "Line pairs where both
wagers can win simultaneously (middles) ... Positive expectation is probabilistic,
never locked. Not arbitrage." `gap_geometry(t_lo, t_hi)` returns `None` when
`t_lo >= t_hi` (no gap: mirror lines or crossed the wrong way -> `NOT_MIDDLE`), and
otherwise returns the gap and the integer outcomes strictly inside it.

**Distinctness is enforced three ways, not just asserted:**

1. **Structurally.** A middle requires DIFFERENT, non-mirror lines at the two legs; M09
   requires the SAME line (or none, for h2h) and a settlement table locked positive in
   every world. `middle_scanner.py`'s module docstring states this and where the two
   engines differ point by point (same-line requirement, simultaneity gating,
   settlement-rule gating dimension, reserved-term discipline).
2. **Mathematically, checked by computation.** `TESTS.py::
   test_middle_worlds_not_locked_positive_at_ordinary_vig` feeds every synthetic
   `MIDDLE_CANDIDATE` fixture's own per-world coefficients through **M09's own**
   `arb_scanner.find_arb_stake_ratio` and asserts no stake ratio makes every world
   strictly positive. **I additionally ran this same cross-check against all 80 real
   `MIDDLE_CANDIDATE` flags produced by the real-tape replay** (Section 4;
   `crosscheck_real.py`, scratchpad, not a repo artifact): `0 of 80` resolved
   locked-positive under M09's solver. This is stated honestly, not as a universal
   theorem: at ordinary vig, the "outside the gap" worlds (one leg wins, the other
   loses) cannot be simultaneously hedged into positive territory, but in the
   degenerate case of an extremely mispriced pair where every world happens to be
   profitable, `TAXONOMY.json` section 1.1's own wording would call that
   `TRUE_CROSS_BOOK_ARBITRAGE` regardless of line equality -- this module does not
   special-case that boundary away, and none of the real or synthetic data exercised
   it.
3. **Vocabulary.** `TESTS.py::test_reserved_term_discipline` checks that
   `M.ALLOWED_VERDICTS` never contains an "ARB"-named value, that no docstring in
   `middle_scanner.py` claims a middle "is" arbitrage, and that no world id this module
   produces is arb-named. This is a precise check (M10's own output vocabulary), not a
   blanket string-absence check -- `middle_scanner.py` legitimately references M09's
   real symbols (`arb_scanner`, `find_arb_stake_ratio`) by name, which the reserved-term
   rule does not prohibit.

**Simultaneity is explicitly NOT a gate for this class**, unlike M09: nothing in the
`MIDDLES_AND_DISLOCATIONS` definition requires simultaneous execution.
`test_simultaneity_recorded_but_not_gating` constructs legs captured 60 minutes apart
and confirms the verdict is still `MIDDLE_CANDIDATE` while `simultaneity.verdict` reads
`NOT_SIMULTANEOUS` -- recorded for criterion 3, never gating the verdict.

**Cross-market dislocations** (the other half of the `MIDDLES_AND_DISLOCATIONS` class,
e.g. F7 spread-vs-h2h coherence) were **not built** by this node. The taxonomy names
both under one class id, but they are a distinct hypothesis family (F7, not F4) with a
different falsification design (no-vig probability coherence across related markets,
not a line-pair gap). Building it honestly would need its own world model and its own
settlement/coherence-tolerance discipline; scoping it into this node would have made
the "never a generic template" requirement (criterion 2) impossible to meet for a
second, under-designed mechanism in the time available. This is a stated gap, not a
silent one.

## 3. Acceptance criterion 2 -- EV models push/half-point semantics per book's actual rules, never a generic template

**Mechanism.** `enumerate_gap_worlds` builds up to 5 discrete settlement worlds from
pure arithmetic on the two thresholds (`BELOW_GAP`, `PUSH_AT_A` only if the leg-A
threshold is an integer, `IN_GAP`, `PUSH_AT_B` only if the leg-B threshold is an
integer, `ABOVE_GAP`) -- basketball margins and totals are integer-valued by
construction, stated as an explicit assumption in the code, not hidden.
`enumerate_gap_worlds_with_dnp` adds a `SUBJECT_DNP` world (both legs void) for
same-player props. `evaluate_middle_settlement` then computes the EXACT profit in
every world using the REAL prices and the venue's OWN, separately-verified
`push_handling`/`void_dnp_handling` rule (`settle_multiplier`, same 3-value vocabulary
as M09: `void_return` / `counts_as_win` / `counts_as_loss`) -- fixtures 4/5 exercise
the SAME geometry (push at leg A) under a nonstandard (`counts_as_win`) vs. standard
(`void_return`) rule and assert different profit numbers, proving the rule is actually
consulted, not templated.

**Where a rule cannot be established, the book is UNSUPPORTED, not assumed:**
`require_push_void_rule`/`require_fee` raise `RuleError` for any venue absent from
`PUSH_VOID_RULES`/`FEE_MODEL`; `evaluate_middle_settlement` catches this and returns
`status="SETTLEMENT_UNSUPPORTED"` with the specific venue(s) and reason(s) named,
rather than defaulting. I searched this repository (`grep -rn
"push_handling|void_dnp_handling|push.{0,20}rule|settlement.{0,20}rule"` across
`experiments/market_program/`) for any prior verification of a real bookmaker's push or
DNP-void rule. **None exists.** The only matches are M09's and M10's own placeholder
tables and the taxonomy's generic prose. `M09_TRUE_ARB_SCANNER/ACTIVATION_CHECKLIST.md`
item 4 independently states the same gap ("Every venue ... has a verified
`SETTLEMENT_RULES` row ... not the ... placeholder ... belongs to whichever node owns
verifying it against each venue's actual rules page"). Per the acceptance criterion's
explicit instruction, **zero real bookmakers are registered in `PUSH_VOID_RULES`** in
this node's tables (registering one without a source would be exactly the
"generic template" the criterion forbids). `coarse_tape_demo.py` registers all 11 real
books with an explicitly-labeled placeholder FEE row only (zero-fee retail, mirroring
M09's own `REAL_BOOK_BASELINE_FEE` justification) -- never a push or DNP-void row.

**EV is never asserted from an invented probability model.** `expected_value(profit,
probabilities)` requires the caller to supply an explicit probability for every
settlement world; absent that, `build_middle_flag` sets `ev.status =
"EV_UNSUPPORTED_NO_PROBABILITY_MODEL"` and `ev.value = None`, with the reason stated on
the flag itself: assigning a probability distribution over margins/totals is S-FUND
territory (`MARKET_PROGRAM_CONTRACT.md` section 2, four-system separation) and out of a
scanning node's scope. `TESTS.py::test_ev_computed_with_probabilities` and
`test_ev_unsupported_without_probabilities` both pass, and
`test_expected_value_rejects_malformed_probabilities` confirms a probability object
that doesn't sum to 1 or doesn't cover the exact world set raises rather than silently
producing a number. **Every one of the 80 real `MIDDLE_CANDIDATE` flags from the tape
replay has `ev.status = EV_UNSUPPORTED_NO_PROBABILITY_MODEL`** -- what IS reported for
every one is the full, real, per-world profit table (see the worked example in Section
4.3), which is the concrete "push and half-point semantics per book's actual rules"
deliverable; what is NOT reported is a scalar edge, honestly.

## 4. Acceptance criterion 3 -- every flag records both legs' capture timestamps and the inter-leg latency window

Every flag (`build_middle_flag`, all verdicts, not just `MIDDLE_CANDIDATE`) carries
`leg_a.capture_ts`, `leg_b.capture_ts` (both witnessed, `fmt_ts` of the actual poll
timestamp), `inter_leg_latency_s` (`abs(t_a - t_b)`), and a full amendment-4-compliant
`simultaneity` block (`t_lower`/`t_upper`, `poll_interval_quote_a/b`,
`vendor_latency_bound`, `clock_skew_bound`, `censor_type`, `tier`, `reason`) reused
directly from M09's `simultaneity_window`. `TESTS.py::
test_capture_timestamps_and_latency_always_present` checks this across every one of the
10 fixtures, including `NOT_MIDDLE` and `SETTLEMENT_UNSUPPORTED` verdicts, so the
requirement is not satisfied only on the headline-positive path.
`test_simultaneity_recorded_but_not_gating` additionally confirms the amendment-4 field
set is present even when simultaneity is `NOT_SIMULTANEOUS` -- recorded, never dropped,
never gating.

### 4.1 What was measured on the real tape, and how

Command: `python coarse_tape_demo.py` from this directory (reads
`C:/Users/jgallagher/wnba-betting-model/data/market_snapshots/snapshots.csv`
read-only; writes only `COARSE_TAPE_DEMO_RESULTS.json` in this node's own directory).
Per-market-kind breakdown independently re-derived with a second, throwaway script
(`breakdown_by_kind.py`, scratchpad, not a repo artifact) calling the exact same
`scan_spread_pairs`/`scan_totals_pairs`/`scan_prop_pairs` functions, to catch any
aggregation error in the combined run:

| market family | rows used (active) | candidate book-pairs | `MIDDLE_CANDIDATE` | `SETTLEMENT_UNSUPPORTED` | `NOT_MIDDLE` |
|---|---|---|---|---|---|
| spreads | 110 | 1,100 | **48** | 112 | 940 |
| totals | 110 | 550 | **32** | 76 | 442 |
| props (4 stat markets combined) | 3,122 | 8,052 | **0** | 329 | 7,723 |
| **total** | 3,342 | **9,702** | **80** | **517** | **9,105** |

`snapshots.csv` had 4,526 total rows at read time (well under the 20,000-row cap; the
whole file was read). All 4,526 rows came from `n_total_rows` measured directly by
`csv.DictReader` iteration, not assumed.

### 4.2 Capture windows -- verify, don't trust, per the dispatch's explicit instruction

The dispatch instructions told me to verify the capture-layer context rather than trust
it: a recently closed node (M26) fixed a bug where the game-lines endpoint wrote zero
rows for an unknown prior period, and game lines only recently began landing. I measured
this directly rather than citing M26's report by assertion:

- **Game lines (spreads+totals): `retrieval_ts` ranges from `2026-08-07T14:03:04.828587
  +00:00` to `2026-08-07T15:22:05.814934+00:00`** -- a **79-minute** window, 220 rows
  total (110 spreads + 110 totals), across exactly **2 games** and **5 distinct polls**.
  This window starts at the EXACT timestamp of M26's own live-verification call
  (`live_verify_defect1.py`, cited in `M26_REPORT_BODY.md` section 1) for the game
  Atlanta Dream @ Washington Mystics -- i.e. this tape's entire game-lines history is
  the M26/M27 live-verification runs themselves, not sustained scheduled-job output.
  **A small game-lines candidate count is therefore a structural artifact of a ~1.3-hour
  capture window that only exists because of a recent bug fix, not evidence middles are
  rare on spreads/totals.** The regular scheduled capture job (`WNBA_MarketLadder`,
  confirmed running every 10 minutes per M27's report) now uses the corrected filter
  going forward, so this window should widen on its own without any action by this
  node.
- **Player props: `retrieval_ts` ranges from `2026-08-06T18:52:04.642477+00:00` to
  `2026-08-07T15:22:05.979490+00:00`** -- roughly **20.5 hours**, 4,196 rows, and this
  is where the tape's real statistical weight is (8,052 of 9,702 candidate pairs, 83%).
  Every one of these pairs, however, lands on `SETTLEMENT_UNSUPPORTED` or `NOT_MIDDLE`,
  never `MIDDLE_CANDIDATE` -- see 4.4.

### 4.3 A worked real example (from `sample_middle_candidate_flags[0]`)

Game `0cc93c06f67e3eeac12f320fbf0a5d2f` (Atlanta Dream @ Washington Mystics), captured
`2026-08-07T14:03:04Z`, spread middle: `betmgm` Atlanta -5.5 at -130 (decimal 1.8696),
`betonlineag` Washington +6.5 at -110 (decimal 1.9091). Gap: margin must exceed 5.5 AND
stay under 6.5 -> **margin == 6 exactly** is the only win-win integer (3 worlds, no push
-- both lines half-point). Real per-$1/$1-stake profit table, computed by
`evaluate_middle_settlement` from these exact prices:

| world | condition | profit |
|---|---|---|
| `BELOW_GAP` (margin < 5.5) | Atlanta loses the -5.5, Washington covers +6.5 | **-0.0909** |
| `IN_GAP` (margin == 6) | both bets win | **+1.7787** |
| `ABOVE_GAP` (margin > 6.5) | Atlanta covers, Washington loses | **-0.1304** |

`inter_leg_latency_s = 0` (both legs captured at the identical poll timestamp).
`simultaneity.verdict = "SIMULTANEITY_UNVERIFIABLE"` (`clock_skew=UNMEASURED`,
`vendor_latency_bounds={}` -- honest, by construction, same discipline as M09's own
demo; this field is descriptive here, not gating). `ev.status =
"EV_UNSUPPORTED_NO_PROBABILITY_MODEL"` -- no claim is made about how likely a
margin-of-exactly-6 outcome is. This is the shape of every one of the 80 real
`MIDDLE_CANDIDATE` flags: small, symmetric-ish losses in the two "miss" worlds (ordinary
vig), a large win if the final margin/total lands in the gap, and an explicitly
unquantified probability of that happening.

### 4.4 Why zero prop middles were fully scored, honestly

All 4,196 prop rows carry half-point lines (`integer_lines` measured as exactly 0 across
the whole tape via a direct scan, `half_lines` = 4,196) -- so **no prop candidate ever
needs a push rule**. But every prop O/U pair carries real DNP risk (the player might not
play), and this module models that honestly via `dnp_risk=True` (`SUBJECT_DNP` world,
both legs void) for every prop pair scanned -- which means every prop candidate that
clears the gap-geometry test STILL needs a verified `void_dnp_handling` row for both
participating venues, and (per Section 3) zero real venues have one. So every prop
`MIDDLE_CANDIDATE`-eligible pair (there were real line gaps: 265 of 1,086 same-poll
same-player groups had >=2 distinct lines across books, measured directly by a scratch
script before writing any code) resolves to `SETTLEMENT_UNSUPPORTED`, never
`MIDDLE_CANDIDATE`. This is the honesty discipline working as designed, not a bug: I
could have gotten a much larger `MIDDLE_CANDIDATE` count by ignoring DNP risk for props,
and chose not to, because doing so would silently misrepresent props as fully specified
when a real settlement dimension is unverified.

## 5. Acceptance criterion 4 -- no order placed or prepared; append-only flag log

- `build_middle_flag` never emits an order-shaped field. `TESTS.py::test_no_order_shape`
  walks every key in a sample flag (recursively) and asserts none matches
  `{side, qty, quantity, order_type, account, order_id, submit, execute}`, and that
  `is_order`/`is_order_intent` are `False`.
  `test_verdict_enum_closed_and_never_order` checks this across all 10 fixtures.
- Output is append-only: `AppendOnlyFlagLog` is reused UNCHANGED from
  `arb_scanner.py` (it is fully generic over any flag dict and holds no venue-table
  state, so importing it carries no risk of leaking M09's mutable tables into M10).
  `TESTS.py::test_append_only_log` appends two flags, then appends a "correction" (the
  same flag again with a `prev_flag_ref`) and asserts the file grows to 3 rows with the
  first two byte-identical to before -- a correction is a new row, never an in-place
  edit, matching `MARKET_PROGRAM_CONTRACT.md` section 6.3's append-only discipline.
- No network calls, no writes outside `experiments/market_program/M10_MIDDLES/` (the
  real-tape demo opens `data/market_snapshots/snapshots.csv` for reading only, verified
  by inspection of `coarse_tape_demo.py`'s own code -- it contains exactly one `open(...,
  "r", ...)` against that path and one `open(..., "w", ...)` against its own
  `COARSE_TAPE_DEMO_RESULTS.json`).

## 6. What could not be established

1. **Real push/void settlement rules for any of the 11 real bookmakers in the tape**
   (`betmgm`, `betonlineag`, `betrivers`, `betus`, `bovada`, `draftkings`, `fanatics`,
   `fanduel`, `lowvig`, `mybookieag`, `williamhill_us`). Searched this repository
   directly (Section 3); none exists. This is the single largest reason the real-tape
   `MIDDLE_CANDIDATE` count (80) understates the number of REAL gaps present (517
   `SETTLEMENT_UNSUPPORTED` candidates have a genuine line gap but an unverified rule).
   Verifying these against each book's actual rules page is out of this node's scope
   (M09's own `ACTIVATION_CHECKLIST.md` item 4 names the same open task) and was not
   attempted -- I did not browse the web or fabricate a rule.
2. **Any probability model for game margins or totals.** No scalar EV is reported for
   any real candidate. This is S-FUND territory per the four-system separation and was
   not built here on purpose, not because it was overlooked.
3. **Whether the 79-minute game-lines window under-samples middles generally**, versus
   how the mix will look once the corrected capture job accumulates more history. This
   node reports the window's exact bounds and its provenance (Section 4.2); it does not
   extrapolate a rate from 5 polls.
4. **Cross-market dislocations** (Section 2) -- not built, stated as scope, not silently
   dropped.
5. **Capacity/stake sizing.** This module deliberately does not solve for an "optimal"
   stake ratio the way M09's arb solver does (there is no locked-positive ratio to solve
   for in a middle) and does not model posted limits -- staking and exposure are S-DEC
   territory (`MARKET_PROGRAM_CONTRACT.md` section 2) and out of scope for a scanning
   node. `world_profit` is reported per $1/$1 unit stake; a caller may rescale.

## 7. Contradictions found

None between `MARKET_PROGRAM_CONTRACT.md` and `TAXONOMY.json` in the sections this node
touches (section 1.2 taxonomy definition, section 6 amendment-4 fields, section 2
four-system separation) -- both state the `MIDDLES_AND_DISLOCATIONS` definition
identically and this module's code implements the JSON wording directly. One
non-contradiction worth recording: the fixture bug caught during development (`middle_
scanner.py` inserting M09's directory at `sys.path[0]` silently shadowed this node's
OWN `fixtures.py` with M09's same-named file, since M09 also has a `fixtures.py`) was
found by `TESTS.py` failing immediately with an `AttributeError` on the first run, not
discovered later -- fixed by appending to `sys.path` instead of inserting at position 0,
with an explanatory comment left in both files so a future editor does not reintroduce
it.

## 8. Stop-condition self-check

No spending, wagers, credentials, scraping/licensing-risk acceptance, or
`SEALED_RESULTS` reads occurred. No reaction-time/timing claim was made without the full
amendment-4 field set (verified by `test_simultaneity_recorded_but_not_gating` and by
direct inspection of every real flag's `simultaneity` block in
`COARSE_TAPE_DEMO_RESULTS.json`). No use of `data/drive_masters/master_odds.csv` (the T2
archive) occurred anywhere in this node -- the real-tape demo reads
`data/market_snapshots/snapshots.csv`, a live-capture poll log with real witnessed
`retrieval_ts` values, not the retrospective single-snapshot archive section 5 of the
contract governs; no `m00_use_class`/`caveat_hash` header applies to this node's
artifacts. The scanner produces flags only -- `TESTS.py` verifies no order-shaped field
ever appears and `is_order`/`is_order_intent` are always `False` across every fixture.
Nothing here trips a stop condition beyond what is reported above.
