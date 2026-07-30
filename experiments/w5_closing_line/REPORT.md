# W5 Closing-Line Groundwork — Cadence Audit + Honest Baselines

*2026-07-30. Produced by `run_w5_baselines.py` (this directory) from
`data/drive_masters/master_odds.csv` (old era) and
`data/odds_capture/master_odds_extension.csv` (new era, built by
`build_odds_master_extension.py` at repo root). Local data only; every number
below is measured, not recalled. Metric throughout: **MAE in spread points on
the home-team spread**. This is a close-prediction leaderboard — it is
deliberately separate from the project's score-differential leaderboard and
must not be merged into it.*

---

## 1. Headline findings

1. **The old master cannot support open/close analysis — the ROADMAP's
   premise was wrong.** `master_odds.csv` (2022–Jul 2025) holds **one
   snapshot per (game, book), taken ~64–65 minutes before tip** (10,000 of
   10,001 game-book pairs have exactly 1 snapshot; the single exception has
   2). The "~5-min cadence" attributed to it in ROADMAP W5 describes the
   upstream Odds API archive it was sampled *from* (visible in its
   `odds_previous/next_timestamp` columns, ~10 min apart), not the file we
   have. Every open/close, T-hour and movement analysis below therefore runs
   on the **new-era captures (2025-07-05 → 2026-07-29)** instead — the exact
   inversion of the plan's "old = rich, new = thin" assumption.
2. **WNBA lines move enough to be worth modeling.** Open→close (median open
   ≈ 28 h out, median close ≈ 2.1 h out): median |move| **0.5 pts**, p90
   **2.5 pts**, mean 1.01; **49.6% of pairs move ≥ 1 pt, 19.7% ≥ 2 pts**;
   31% don't move at all. Movement accelerates near tip: ~0.03 abs
   pts/elapsed-hour beyond 72 h out vs **~0.09 pts/hour inside the last
   hour** (~3× faster).
3. **Honest baseline floor:** predicting *close = open* errs **1.01 pts**
   (2025: 0.96, 2026: 1.06). Later lines dominate earlier ones monotonically
   on same samples (line@T−24h 1.13 vs open 1.31 on the same pairs; T−6h
   0.58). Any future closing-line model must beat the *current line*, not
   the open — the current line is the real incumbent.
4. **First model row (ridge on current line, hours-to-tip, movement-so-far;
   train 2025 → test 2026): 1.007 MAE vs 0.980 for "close = current line"
   on identical test rows. The ridge does NOT pass the W5 validation gate.**
   The current line is already ~the market's best estimate of the close at
   this cadence; beating it will require genuinely new information (W1
   news/availability flow), not transforms of the line path.

---

## 2. Part A — Old master (2022–2025) cadence audit (measured)

Universe: home-team rows of `data/drive_masters/master_odds.csv`
(10,002 rows; 817 events; 10,001 game-book pairs; 22 books overall).

| season | events | games w/ game_id | game-book pairs | books | max snaps/pair | min-before-tip p10/p50/p90 |
|---|---|---|---|---|---|---|
| 2022 | 181 | 180 | 2,234 | 16 | 2 | 65 / 65 / 65 |
| 2023 | 260 | 259 | 3,826 | 18 | 1 | 64.3 / 64.3 / 64.4 |
| 2024 | 262 | 261 | 2,817 | 13 | 1 | 64.4 / 64.4 / 64.4 |
| 2025 (→Jul 4) | 114 | 113 | 1,124 | 11 | 1 | 64.4 / 64.4 / 64.4 |

- 99.99% of pairs have exactly **one** snapshot; `odds_odds_time_check` =
  commence − 1 h (the requested archive time), actual snapshot ≈ 64–65 min
  before tip on the API's 5-min grid.
- **Consequence:** open, close, |close−open|, and T-hour baselines are
  undefined on this file. What it *does* support: a clean **T≈1 h line** per
  game-book for 813 games across 2022–2025 — usable later as a benchmark
  input, and for cross-book dispersion studies.
- Per-book game coverage by season: `old_master_coverage_by_book.csv`
  (book availability varies hard across seasons: 16 → 18 → 13 → 11 books).
- 94 rows in the old master carry no `game_id`; left as-is (not this task's
  scope to repair).

**Recovering the old era at real cadence** would require a paid Odds API
historical sweep (the archive exists upstream at 5–10 min grid); nothing on
disk contains it. Until then, 2022–2025 contributes no training rows to a
closing-line model.

## 3. Part B — New era (2025-07-05 → 2026-07-29): open/close study

Universe: `master_odds_extension.csv`, home-team spread rows of **completed
games** (`game_id` present), snapshots **strictly before tip** only
(in-play rows excluded by timestamp; tip = commence quoted at the game's
latest listing, which resolves the two reschedule events noted in §5).
That leaves **13,451 snapshot rows → 4,439 (game, book) pairs, 406 games,
11 books** (2025: 2,151 pairs; 2026: 2,288).

Cadence reality (2 captures/day at 15Z/22Z, games listed ~1.5 days ahead on
median): snapshots per pair p25/p50/p75/max = 2/3/4/8; **median open ≈ 28.1 h
before tip; median close ≈ 2.1 h before tip** (p90 4.1 h — evening games'
"close" is the 6 pm ET capture; this is NOT the true T→0 closing line, see
§6).

### |close − open| distribution (spread points)

| season | pairs | p50 | p75 | p90 | p95 | max | mean | =0 | ≥1 pt | ≥2 pts |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 4,439 | 0.5 | 1.5 | 2.5 | 3.5 | 7.0 | 1.012 | 31.2% | 49.6% | 19.7% |
| 2025 | 2,151 | 0.5 | 1.5 | 2.5 | 3.5 | 6.0 | 0.957 | 34.4% | 44.7% | 18.8% |
| 2026 | 2,288 | 1.0 | 1.5 | 3.0 | 3.5 | 7.0 | 1.063 | 28.1% | 54.2% | 20.5% |

### Baseline leaderboard — predicting the close (ALL = 2025+2026 pooled)

A pair is **degenerate** for horizon T when the last snapshot at/before
tip−T *is* the close snapshot itself — the "prediction" trivially equals the
target. With 2/day captures this dominates T ∈ {3, 1}: read `mae` there as
vacuous and use `mae_nondeg` (matinee-pattern pairs only). `mae_open_same`
re-computes close=open on exactly that row's subsample, making columns
comparable.

| baseline | mae | n pairs | degen. share | mae_nondeg | n_nondeg | mae_open_same |
|---|---|---|---|---|---|---|
| close = open | 1.012 | 4,439 | 5.6%* | 1.071 | 4,192 | 1.012 |
| close = line@T−24h | 1.133 | 2,863 | 0.2% | 1.135 | 2,857 | 1.308 |
| close = line@T−12h | 1.109 | 3,066 | 0.3% | 1.112 | 3,057 | 1.291 |
| close = line@T−6h | 0.584 | 4,223 | 1.3% | 0.592 | 4,166 | 1.063 |
| close = line@T−3h | 0.366 | 4,374 | 42.7% | 0.639 | 2,507 | 1.027 |
| close = line@T−1h | 0.036 | 4,432 | **95.3%** | 0.763 | 209 | 1.013 |

\* for close=open, "degenerate" = single-snapshot pairs (open *is* close).

Per-season tables: `baseline_mae_by_season.csv` (2026 lines move slightly
more than 2025 at every horizon). Reading: information arrives
monotonically — on same samples the T−24h line beats the open (1.133 vs
1.308) and T−6h roughly halves the open's error (0.584 vs 1.063).

### Per book (pooled, close=open)

`baseline_by_book.csv`. Range: betus 0.66 (but it lists latest —
mean 2.3 snapshots/pair, so its "open" is already late) to
fanduel 1.145 / draftkings 1.155 (earliest listers, 3.4–3.5 snapshots/pair).
**Caveat: per-book open→close MAE conflates line volatility with listing
depth; don't read it as "sharpness" without conditioning on open time.**
All 11 books cover essentially all 406 games (betmgm 382).

### Movement by hours-to-tip (consecutive snapshot steps)

| hrs-to-tip bucket | steps | mean abs move/step | % steps ≠ 0 | mean step hrs | abs pts per elapsed hour |
|---|---|---|---|---|---|
| ≥72 | 29 | 0.36 | 48% | 13.2 | 0.027 |
| 48–72 | 83 | 0.25 | 27% | 7.1 | 0.035 |
| 24–48 | 1,908 | 0.54 | 48% | 8.0 | 0.068 |
| 12–24 | 380 | 0.55 | 54% | 7.0 | 0.078 |
| 6–12 | 2,446 | 0.97 | 75% | 18.3 | 0.053 |
| 3–6 | 1,659 | 0.52 | 55% | 9.6 | 0.054 |
| 1–3 | 2,298 | 0.63 | 60% | 8.0 | 0.079 |
| <1 | 209 | 0.76 | 73% | 8.3 | 0.092 |

The 6–12 h bucket's big per-step move rides the overnight 22Z→15Z gap
(~17 h) — that's where injury-report news lands; per-elapsed-hour the drift
is flat-ish overnight and fastest inside the final hours. **Signal
available to a closing-line model ≈ 1.0 pts of open→close movement, of
which ~0.4–0.5 pts is still unrealized at T−6h.**

## 4. Part C — First model row: ridge (clearly labeled, walk-forward)

Samples: every pre-tip snapshot strictly earlier than its pair's close
snapshot (features computable at snapshot time: current home spread,
hours-to-tip, movement-so-far = current − open-so-far). **Train = 2025
season (4,014 rows); test = 2026 (4,998 rows).** Closed-form ridge, λ=1.0
fixed (numpy; sklearn unavailable), features standardized on train stats.
The planned train 2022-23 / test 2024-25 split is impossible — no
multi-snapshot data exists for those seasons (§2).

| model (test = 2026 snapshot rows) | test MAE |
|---|---|
| **baseline: close = current line** | **0.980** |
| ridge(current, hrs_to_tip, move_so_far), λ=1 | 1.007 |
| baseline: close = open | 1.279 |

Standardized coefficients (`ridge_coefficients.csv`): current 8.035
(≈ raw slope 1.01 — the model is ~identity on the current line),
hrs_to_tip −0.040, move_so_far −0.046 (both ≈ noise-level).

**Verdict: fails the W5 validation gate** (does not beat close=current;
beats close=open only because current does). At 2/day cadence the current
line already embeds nearly everything the line path knows about the close.
The gate-passing path is exogenous features — W1 news/availability flow
timestamped between snapshot and tip — not curve-fitting the path.

## 5. Extension build (Part 1 deliverable, context for the above)

`build_odds_master_extension.py` → `data/odds_capture/master_odds_extension.csv`
(**27,734 spread rows**, 17 columns identical to the old master; 2025:
12,456 / 2026: 15,278) + `master_odds_extension_other_markets.csv`
(**53,178 rows**: totals 27,820, h2h 25,358; same shared columns with
`market_key`/`outcome_name`/`outcome_point`/`outcome_price` replacing the
spread triplet). 294 snapshot files parsed (292 hist + 2 live).

- **415 unique events → 406 matched to completed games (of 519 completed
  games in the refresh gamelogs; the other 113 predate the 2025-07-05
  capture start and are the old master's territory). Zero unexplained
  unmatched events.** Every completed game inside the capture window has
  odds — 406/406.
- Match kinds: 406 exact (ET-date + home + away vs gamelogs; UTC→ET via
  `America/New_York`), 2 hand-adjudicated reschedules (documented in-script:
  playoff Game 2 provisional listing → `1042500212`; postponed 7/16→7/20
  DAL-NYL → `1022600183`; both games therefore have 2 `api_event_id`s),
  1 intentionally unmatched non-gamelog event (NYL–LVA 6/30/2026 during a
  league-wide schedule gap — the Commissioner's Cup final pattern; it has
  no regular-season GAME_ID by design), 6 future games (7/30–7/31, not yet
  in gamelogs).
- Automated ±1-day/side-swap fallbacks were **removed** after the ±1-day
  rule produced a provably wrong match (grabbed playoff Game 1 for Game 2's
  provisional listing). Resolution is exact-match-else-explicit-override.
- 232 in-play spread rows (snapshot ≥ commence) are kept in the extension
  (real captures, identifiable by timestamps) and excluded from all
  analysis here. Validation: every (event, book, snapshot) has exactly 2
  spread rows summing to 0; team names always ∈ the 15 franchises; no null
  spreads/prices.

## 6. What transfers to which cadence — and what W5 needs next

- Everything in §3–§4 is native to the **2/day cadence** and transfers
  forward as-is to the live capture (same 15Z/22Z-ish grid).
- **The "close" here is the ~T−2h line, not the true close.** Baselines at
  T ∈ {3, 1} are mostly degenerate at this cadence; a real closing-line
  target needs a capture at/near tip. Cheapest fix: one extra live pull per
  game day at ~23:30Z (~3 credits/day) or per-game T−15min pulls; either
  turns the degenerate T−1h row into a measurable one.
- The old master contributes a T≈1h line for 813 games 2022–2025 — usable
  as a *benchmark/feature at that single horizon* once a model exists, but
  no training sequences. A paid historical sweep is the only way to build
  pre-2025 open/close data.
- 2025 here = Jul 5–Oct 10 only (post-All-Star + playoffs); 2026 = May 8–Jul
  29. Season labels are honest but partial-season — don't read 2025 vs 2026
  differences as season effects.

## 7. Files

| file | contents |
|---|---|
| `run_w5_baselines.py` | reproduces everything: `python experiments/w5_closing_line/run_w5_baselines.py` |
| `old_master_cadence_audit.csv` | §2 per-season audit |
| `old_master_coverage_by_book.csv` | old-master games per season × book |
| `extension_game_book_openclose.csv` | per (game, book): open/close spreads, timestamps, hours-to-tip, n snapshots |
| `baseline_mae_by_season.csv` | §3 leaderboard, per season + pooled |
| `baseline_by_book.csv` | §3 per-book close=open + listing depth |
| `movement_distribution.csv` | §3 movement percentiles |
| `movement_by_hours_bucket.csv` | §3 step movement table |
| `ridge_model_result.csv`, `ridge_coefficients.csv` | §4 model row + feature importances |

Upstream: `build_odds_master_extension.py` (repo root) →
`data/odds_capture/master_odds_extension{,_other_markets}.csv`.
