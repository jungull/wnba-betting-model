# M05 design baseline — adoption and reconciliation record

**Node:** M05_EVENT_MARKET_LINKAGE · **Date:** 2026-08-06

## 1. What this file is

The linkage design was drafted before this node existed, as the pre-node
research effort `experiments/market_program/W1_DRAFTS/EVENT_LINKAGE_AND_METHODOLOGY.md`.
That draft is now **frozen by hash in the M00 contract itself** (§0.4:
sha256 `5d91f6d36c15b14fa57ef070a544dc4ca2df876f4b217c0fafa667ee1d13854d`,
re-verified byte-identical at M05 execution time — see REPORT.md §2).

The M05 acceptance criterion says the draft "lands under this node's
directory and is reconciled, not duplicated." Copying the file here would
duplicate a contract-frozen artifact and create two hashables that could
drift. This file is therefore the **adoption record**: it pins the draft by
hash, declares its §A and §B the binding specification for the code in this
directory, and enumerates every point where the implementation had to make
a decision the draft left open — or where the draft contradicts itself.
Nothing in the draft is restated except where a delta exists.

## 2. Adopted verbatim (no delta)

- §A.1 event definition, first-seen keying on OUR `capture_utc`; vendor
  stamps carried, never keyed on (`advisory` field; TESTS T20).
- §A.2 quote-change definition and structural in-play exclusion (T12).
- §A.3 window set (PRE / POST_FIRST / H+1..H+60 / CLOSE), ambiguity
  excluded not resolved (T05), truncation at commence (T11).
- §A.4 report_id clustering; one report = one composite observation for
  game-level series (T08); same-poll pile-ups mutually confounded (T09).
- §A.5 suspensions (T07); out-of-hours wide intervals never patched (T06).
- §A.6 frozen, hashed ER map; normalized-exact + explicit O14-format alias
  table; **no fuzzy path exists in the module** (T10). Normalization is the
  O14 `_norm_name` verbatim.
- §A.7 exclusion-not-patching; the ten reason codes verbatim (T19).
- §A.8 determinism: `link()` is a pure function; canonical JSON; config,
  ER-map, and poll-log hashes recorded on every result (T02).
- §B.1 three-term widening; §B.2 interval-only reaction bounds with the
  amendment-4 mandatory field set (T01, T06, T13); §B.3 sharpness
  prohibition incl. `INDISTINGUISHABLE_AT_GRID` (T14, T17); §B.5 advisory
  channel separation (T20).

## 3. Reconciliation deltas (implementation decisions, frozen here)

**DB-1 — §A.2 internal contradiction: `line` in the series key vs
"line moved" as a quote-change kind.** The draft defines a quote series on
`(game_id, bookmaker, market, outcome, line)` and simultaneously lists
"line moved" among the changes a series can exhibit. Both cannot hold: if
the line is part of the key, a line move ends one series and starts
another, and no series ever exhibits a LINE_MOVE. Resolution (frozen):
`point`/`line` is series **state**, not key, for game-level markets
(`series_key_includes_line = false` in config); LINE_MOVE is then a
detectable change kind. The config flag allows per-line keying for
alternate-line props designs later. This contradiction is also reported in
REPORT.md §6.

**DB-2 — player resolution requirement is scoped to the linkage that needs
it.** Game-level relevance (injury/report event → that game's h2h/spread/
total series) requires resolved team and game identities; those fail
closed. A resolved `player_id` is attached when the identity index
resolves it, but its absence does not fail a game-level link (the report's
team and game are the joined entities). Player-prop series linkage DOES
require a resolved `player_id` and no fuzzy path exists. On the real-tape
probe the player map is the O14 alias table (empty by design) plus nothing:
attaching a full player identity index is a capture-side precondition
(§A.6 direction to the capture owner), not something M05 may improvise
from a bulk read of the possession masters.

**DB-3 — §A.3 rule 2 operationalization.** "If the series' local poll
spacing around the anchor exceeds `h`, the `H+h` window is emitted as
`UNRESOLVED_AT_GRID`" is implemented as two frozen tests, in order:
(a) if the EVENT interval's own width exceeds `h·60` the window is
`POLL_GAP_EXCEEDS_HORIZON` (§A.5: a wide-interval observation is unusable
in any window narrower than its own width);
(b) else if no successful QUOTE poll exists in `(e_up, e_up + h·60]` the
window is `UNRESOLVED_AT_GRID`.
This gives the two codes disjoint meanings: POLL_GAP = the event side is
too coarse; UNRESOLVED_AT_GRID = the quote side is too coarse. On the
current tape (both sides ~hourly) POLL_GAP dominates — see REPORT.md §5.

**DB-4 — reason-code architecture.** Six codes act at record level
(ENTITY_UNRESOLVED, TIER_INSUFFICIENT, IN_PLAY_ONLY, CLOCK_UNBOUNDED,
SUSPENDED_ACROSS_EVENT, AMBIGUOUS_PRE) with a frozen precedence order;
CONFOUNDED@h, UNRESOLVED_AT_GRID, POLL_GAP_EXCEEDS_HORIZON and
TRUNCATED_AT_COMMENCE are per-window codes that become record-primary in
the degenerate cases (POST side confounded → `CONFOUNDED@POST`; no
post-event pregame poll → TRUNCATED_AT_COMMENCE). Every record still
carries exactly one primary reason (§A.7); every window carries its own
status. All ten codes are exercised by TESTS T19.

**DB-5 — isolation guard.** §A.4's guard "default: one poll interval" is
frozen as one EVENT-stream poll interval measured at the event's own
anchor from the actual poll log (median gap fallback only for the
degenerate first-poll case, which cannot arise for a transition event).

**DB-6 — composite merge rule.** Events sharing `report_id` AND an
identical censoring interval merge into one composite per series. Same
report re-sighted at a later poll (amended report) is a distinct
observation and is handled by the isolation predicate, not merged.

**DB-7 — report identity.** `report_id = H(stream, [source, report_date,
t_seen])`: one source's report for one report_date, as sighted at one
poll. Frozen in the adapters; a future official-report version field can
replace `t_seen` by amendment to this file, which forces a full re-run
(§A.6 discipline).

**DB-8 — right-censoring anchor.** For a series with no post-event change
before CLOSE, the right-censored claim's lower bound anchors on the last
pregame observation instant (widened per B.1); `t_upper = INF`,
`censor_type = "right"` (T13).

## 4. What this file does NOT do

It does not modify the draft, the contract, or TAXONOMY.json; it does not
add hypothesis families; it does not touch §C (ratified verbatim into the
contract and enforced there); it makes no timing claim of any kind.
