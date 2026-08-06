# BOOKIE_BASELINE — the market's own accuracy against realized outcomes

**Node:** `experiments/market_program/BOOKIE_BASELINE/` · **Lane:** market_intelligence
**Governed by:** `MARKET_PROGRAM_CONTRACT.md` (sha256
`1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de`) and
`D034_GRADUATION_STANDARD` (`experiments/player_program/orchestration/DECISION_LEDGER.jsonl`).

## Epistemic status

This node measures **the bookmaker market**, never any model this program builds. It never touches
`experiments/player_program/stage2b/SEALED_RESULTS`. Nothing here is a fundamental prediction, a
timing claim, a CLV claim, or an executability claim. Vig removal is delegated to
`M11_CONSENSUS_MODEL/consensus.py` — the vig-removal method (`multiplicative_proportional`) and
its preregistration were frozen by M11 before this node ran any evaluation; this node changed
nothing in M11 and invoked it as machinery only, per D034's standard that **de-vigged threshold
probabilities are the primary identified quantity**. No distributional assumption about the
scoring margin is used anywhere in this report — the moneyline side is evaluated as a de-vigged
win/loss threshold probability only; the spread and total sides are evaluated as point-line
accuracy against the realized margin/combined score directly (MAE and bias), never converted to or
compared against an implied probability distribution.

## The unknown-snapshot-time caveat — FROZEN TEXT, carried on every output row

> "This snapshot's timestamp is vendor-asserted and unwitnessed (tier T1:
> THIRD_PARTY_CONTEMPORANEOUS, per MARKET_PROGRAM_CONTRACT.md section 4.3). It is drawn from a
> third-party historical-odds archive retrieved on 2026-08-06, labelled EARLY (vendor-asserted
> ~16:00Z request) or LATE (vendor-asserted ~23:30Z request) relative to the archive's own request
> day, not from our own real-time capture. LATE is closer to commence than EARLY, but neither is a
> witnessed closing line, and the true hours-to-commence at capture is not independently verified.
> No timing, latency, reaction, or CLV inference may be drawn from this snapshot; it supports
> calibration-against-realized-outcomes only, at an unknown-but-bounded-pregame instant."

`caveat_sha256 = 93a816cc9357af8d0a09da60695eee60e6921b1cbf1fbcb2b7c8b125216e21f7` (verified against
the frozen constant by `TESTS.py::test_caveat_hash_matches_text`). Every row of
`baseline_metrics.json` and every number in this report inherits this caveat structurally — it is
not a footnote, it bounds what the numbers below mean. **Note also that this archive is NOT the T2
`master_odds.csv` object that `MARKET_PROGRAM_CONTRACT.md` section 5 bounds**; that section's
enumerated use classes (M00-U1..U6) govern a different, single-snapshot-per-game object and do not
apply here. This archive's own provenance fields (`provenance_class: T1_VENDOR_ASSERTED`,
`vendor_ts_semantics: vendor_asserted_unwitnessed`, inspected directly on the first two archive
lines) place it under section 4.3's T1 tier rule instead, which this caveat discharges.

## Inputs (read-only; owned data; no network, no git, no subagents)

| Input | Path | Role |
|---|---|---|
| T1 odds archive | `data/market_snapshots/historical/featured_backfill.jsonl` (LIVE worktree `C:/Users/jgallagher/wnba-betting-model`) | 1,415 archive lines, 1,264 distinct games, two snapshot classes/day |
| Game outcomes | `data/masters/master_team.parquet` (this worktree) — a team-level aggregate of the `wnba_gamelog_*` box-score family with `game_date`/`is_home`/`pts`/`opp_pts` fields the raw player-level `wnba_gamelog_*.parquet` files do not carry directly | realized home/away final scores, 2021–2026 |
| De-vig / consensus machinery | `experiments/market_program/M11_CONSENSUS_MODEL/consensus.py` | delegated, never reimplemented |

`master_team.parquet` was used instead of hand-aggregating the raw `wnba_gamelog_*.parquet` player
box scores because it is the only owned artifact carrying `game_date`, `is_home`, and per-team
`pts`/`opp_pts` in one row — fields the raw gamelog files (player rows only, no date, no home/away
flag) do not expose. It is the same box-score family (`source` column values trace to
`gamelog_team_<season>_<season_type>.parquet` + misc-stats patches), not a different data source.

## Methodology

**Snapshot classes.** Archive lines were bucketed by the hour of `requested_ts`: `16` → **EARLY**,
`23` → **LATE** (the two request hours actually observed in the archive; no other hour occurs).
Because the source archive represents the market's full upcoming-game board at each request (a game
can appear in many days' worth of requests before it is played), for each game and each class this
node used **the single request whose `requested_ts` is latest but still `<=` the game's
`commence_time`** — i.e., that game's own EARLY and LATE observation, closest to tipoff for that
class. Any candidate row with `vendor_snapshot_ts >= commence_time` was excluded structurally before
this selection (435 of 4,899 payload game-appearances; contract section 4.4, in-play exclusion).

**Cross-book vs. best-book.** `cross_book` is M11's uniform-weight, T1-admitted, multiplicative-devig
consensus (moneyline) or the simple arithmetic mean of contributing books' point lines (spread/total
— M11 has no point-line consensus function; this node computes the mean directly and documents that
choice here rather than extending M11). `best_book` uses a single reference book, **FanDuel**,
selected because it is the most frequently present book in the archive (4,719 of the archive's
game-appearances carry a FanDuel quote — the next closest is DraftKings at 4,278; full book-frequency
counts are not persisted to a file but were measured directly against the archive and are reproducible
from `build_baseline.py`'s `PRIMARY_BOOK` selection comment).

**Sign convention (spread).** A book's spread `point` is quoted per team (e.g. home team `-8.0` means
home favored by 8). Predicted home margin = `-1 * home_team_point`. Actual home margin =
`home_pts - away_pts`. Error = predicted − actual. Verified against known-answer fixtures in
`TESTS.py`.

**Sign convention (total).** Predicted total = the market's `Over`/`Under` point (both sides carry
the same point). Actual total = `home_pts + away_pts`. Error = predicted − actual.

**Moneyline.** Per book, `no_vig([home_price, away_price])` (M11, `multiplicative_proportional`,
preregistered before this node ran) gives the home win probability; `cross_book` averages across
T1-admitted books uniformly (M11's default `weights_status="PREREGISTERED_UNIFORM"` — no fitted
weighting is used anywhere in this report); `best_book` uses FanDuel alone when present. Brier score,
log loss, and a 10-bin calibration table (bin width 0.1 on predicted home win probability) are
reported per row.

**Team-name → gamelog join.** The archive's 16 distinct team names (including one national-team
exhibition opponent, "Nigeria", which is out of the gamelog universe and reported unmatched) were
mapped to `master_team.parquet`'s `team_abbreviation` values by direct inspection (see
`build_baseline.py::NAME_TO_ABBR`; franchise-rename seasons — Phoenix Mercury `PHO`→`PHX` — carry
both candidate abbreviations). `commence_time` (UTC) was converted to an estimated Eastern date by
subtracting 4 hours (WNBA's season runs entirely within EDT, UTC−4; this is an approximation, not a
verified per-game timezone lookup, and is stated here structurally rather than footnoted). A game is
matched to the exact-date row for its team pair if exactly one exists; only if no exact-date row
exists does a ±1-day fallback window apply, and only if that window is unambiguous (exactly one row).
Any pair with zero or multiple ties, at either stage, is reported unmatched/ambiguous — **never
guessed** (verified in `TESTS.py`).

## Join audit — every unmatched game listed, none silently dropped

| | n |
|---|---|
| Archive lines | 1,415 |
| Payload game-appearances (pre in-play filter) | 4,899 |
| In-play rows excluded structurally (`vendor_snapshot_ts >= commence_time`) | 435 |
| Distinct games in archive (post in-play filter) | 1,264 |
| **Matched to a realized outcome** | **1,250 (98.9%)** |
| **Unmatched** | **14 (1.1%)** |

All 1,250 matches were `MATCHED_EXACT_DATE` (zero ±1-day fallback matches were needed among games
that resolved). The full unmatched list, with reasons, is in `join_audit.json`; summary:

| Reason | n | Notes |
|---|---|---|
| `NO_MASTER_ROW_WITHIN_1_DAY` | 11 | No matching team-pair/date row within ±1 day. Four of these cluster on **2026-05-03**, suggesting either an early-2026-season scheduling discrepancy between the archive and the gamelog build, or games not yet reflected in `master_team.parquet` at the time it was built; not independently resolved further by this node. |
| `AMBIGUOUS_WITHIN_1_DAY_2_ROWS` | 1 | Las Vegas @ Indiana, Sept 2025 — two same-pair games fall inside the fallback window; correctly refused rather than guessed. |
| `NO_MASTER_ROW_FOR_TEAM_PAIR` | 1 | Portland Fire @ Los Angeles Sparks, 2026-05-03 — team pair not found in `master_team.parquet` at all. |
| `NO_ABBR_MAPPING` | 1 | Indiana Fever vs. "Nigeria" — a national-team exhibition, outside the WNBA gamelog universe by construction. |

## Results — pooled across all seasons

Two snapshot classes (EARLY / LATE) × two variants (cross_book / best_book). Full per-season
breakdown (2022–2026, `Regular Season` + `Playoffs` pooled by whichever season the matched game
falls in) is in `baseline_metrics.json`; only pooled rows are inlined here for readability.

| Class | Variant | Spread MAE | Spread bias | Total MAE | Total bias | Brier | Log loss | n (ML) | avg books (h2h) |
|---|---|---|---|---|---|---|---|---|---|
| EARLY | cross_book | 9.527 | +0.074 | 13.599 | −0.968 | 0.2007 | 0.5866 | 1,248 | 11.6 |
| EARLY | best_book | 9.522 | +0.118 | 13.585 | −1.016 | 0.2006 | 0.5866 | 1,245 | — |
| LATE | cross_book | 9.697 | +0.024 | 13.743 | −0.891 | 0.2020 | 0.5894 | 1,068 | 10.1 |
| LATE | best_book | 9.683 | +0.033 | 13.785 | −0.964 | 0.2014 | 0.5873 | 1,053 | — |

Bias sign convention: positive = market line runs higher than the realized value on average
(spread: predicted home margin overshoots actual; total: predicted total overshoots actual — note
totals are *negatively* biased pooled, i.e. actual totals ran higher than the market number on
average).

Both classes and both variants land in a narrow band (spread MAE ≈ 9.5–9.7, Brier ≈ 0.200–0.202):
cross-book and best-book track each other closely at this coverage level (11–12 books per game on
average), and LATE is not measurably more accurate than EARLY on this archive — consistent with the
caveat above that neither is a verified close and both may be many hours from actual tipoff for a
given game.

### Moneyline calibration — pooled, LATE, cross_book (10-bin, n=1,068)

| Predicted p(home win) bin | n | Mean predicted p | Empirical home win rate |
|---|---|---|---|
| [0.0, 0.1) | 4 | 0.087 | 0.250 |
| [0.1, 0.2) | 67 | 0.162 | 0.224 |
| [0.2, 0.3) | 103 | 0.255 | 0.223 |
| [0.3, 0.4) | 124 | 0.353 | 0.339 |
| [0.4, 0.5) | 120 | 0.447 | 0.417 |
| [0.5, 0.6) | 147 | 0.549 | 0.537 |
| [0.6, 0.7) | 188 | 0.648 | 0.676 |
| [0.7, 0.8) | 152 | 0.752 | 0.697 |
| [0.8, 0.9) | 131 | 0.848 | 0.855 |
| [0.9, 1.0) | 32 | 0.914 | 0.938 |

The de-vigged market probability tracks the empirical win rate closely across bins (all bins within
roughly ±0.06 of the diagonal, most within ±0.03); the lowest two bins (n=4, n=67) show the market
slightly *underrating* home teams there (empirical rate above predicted), which is a small-n
artifact in the bottom bin (n=4) and plausibly a real but modest effect in the second bin — not
tested further here (no preregistered F5 endpoint was run; this is descriptive calibration only,
per this node's mandate, not a family-endpoint claim under the M00 evidence ladder). Full 10-bin
tables for every season/class/variant combination are in `baseline_metrics.json`.

## Coverage

Average book count per game fell from ~11.6 (EARLY) to ~10.1 (LATE) pooled — fewer books post
quotes at the later request hour than the earlier one, on this archive. By season, average h2h book
coverage ranged from a high of 14.3 (2023) to a low of 8.6–9.8 (2024–2026 LATE), a declining trend
worth independent investigation but out of this node's scope (this node measures market accuracy,
not why the archive's book count declined).

## Observations (descriptive; not evidence-ladder claims)

* **2026 totals ran notably higher than the market's number**: pooled 2026 total bias is
  approximately −3.6 (both classes, both variants) versus −0.5 to −1.0 in every prior season. This
  node does not investigate the cause (rule change, pace change, or a data-quality issue in the 2026
  slice of `master_team.parquet`) — it is reported as a measured fact, not explained.
* Moneyline Brier score is best (most accurate) in 2024 (≈0.188) and worst in 2025 (≈0.212); spread
  MAE is best in 2024 (≈8.2–8.4) and worst in 2025 (≈10.4–10.5). Both point the same direction in the
  same season, which is consistent (a market that prices win probability better also prices margin
  better) but not independently tested for a common cause.

## What this node could NOT establish

* Which book quote within a snapshot line is closest to actual game time for any *individual* game —
  the vendor timestamp is asserted, not witnessed (T1), so "LATE is closer to commence than EARLY"
  is a population-level statement about the request schedule, not a per-game verified fact.
* Why 11 games cluster as unmatched around 2026-05-03 specifically — not resolved beyond listing the
  reason code; plausibly a schedule/build-timing artifact, not investigated further.
* Any causal explanation for the 2026 total-bias shift or the coverage decline — both reported as
  measured, neither explained.

## Reproducing

```
python experiments/market_program/BOOKIE_BASELINE/TESTS.py       # fixture tests, known answers
python experiments/market_program/BOOKIE_BASELINE/build_baseline.py   # full measurement pass
```

Outputs: `baseline_metrics.json` (all seasons × classes × variants, full calibration tables),
`join_audit.json` (every unmatched game, with reason), `outcome_rows.json` (per-game/per-class raw
detail row: book counts, cross-book p(home), realized outcome).
