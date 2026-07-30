# ROADMAP — WNBA Prediction Engine

*Created 2026-07-30; revised same day after John's methodology review. Supersedes the phase
outline in `project_docs/HANDOFF.md` §6 (kept unchanged as historical record). The HANDOFF §3
constitution remains binding with two amendments recorded below (odds rule, no-imputation rule).*

## The three systems

This project is **three separate systems** sharing data infrastructure but with separate
targets, separate gates, and separate leaderboards. A model may never "win" through timestamp
ambiguity, metric choice, or repeated experimentation.

1. **Basketball forecasting model** — predicts game outcomes from basketball information only.
2. **Market / closing-line model** — predicts market behavior from market information.
3. **Betting decision & bankroll system** — combines 1 and 2 into risk-controlled decisions.

### Amended constitution rules
- **Odds rule (amends HANDOFF §3.7):** odds and market-derived variables are **prohibited in
  the basketball outcome model**. They are **permitted in the separately trained market model
  and the betting decision layer**. Benchmarking against the market remains universal.
- **No-imputation rule (amends HANDOFF §3.8):** never fabricate or silently fill historical
  truth. At prediction time, missing information must produce an explicit missing state, a
  validated fallback model, or **no prediction / no bet**. ("Go get the real data" governs
  historical collection; live systems degrade explicitly, never silently.)

---

## The prediction contract (governs everything downstream)

Every forecast is made at a named **decision time** and may use only information observably
available before its cutoff. Every model is compared against the **market line available at
the same cutoff** — the close is a separate, later benchmark and the CLV outcome measure.

| Forecast | Decision time | Outputs | Market comparison |
|---|---|---|---|
| Early | T−24h | home & away score distributions, margin/total distributions | line at T−24h |
| Morning | T−8h | same | contemporaneous line |
| Pregame | T−90m | same | contemporaneous line |
| Final | T−30m | same | contemporaneous line |

**Provenance fields required on every feature row:** `event_time`, `published_time`,
`observed_time`, `forecast_cutoff`, `source`, `source_version`. Applies with special force to
injury designations, starters, referee assignments, news items, and corrected/refetched PBP
files. A feature whose availability time cannot be established is not a feature.

**Information-parity caveat:** the contemporaneous line is the correct benchmark for
decision-time fairness, but the market at T−24h may already hold availability information
absent from any historical reconstruction (practice participation, travel/rest decisions,
minutes restrictions already priced in). Historical model-vs-market comparisons carry that
residual disadvantage; it is acknowledged in reports, never assumed away.

---

## Phase 0 — Continuous data certification (never "done")

Collection status 2026-07-30: gamelogs/pbp/misc/advanced complete or completing tonight
(2023 paint repaired 50/50; granular backfill running); odds 2022→now continuous (July-2025
gap backfilled, 292 snapshots); official injury designations captured live (2×/day → hourly
as of tonight); 202,987 shot locations (all seasons); starters/stints derived from all 1,424
PBP games (median minutes error 0.00); historical injury archive crawling; officials crawl
queued; full audit + data commit tonight.

**Standing daily certification** (`daily_certify.py`, scheduled; failures alert, never
auto-fix): schema drift; duplicate games/players; game-ID reconciliation across sources;
point-in-time availability of every capture; coverage by season × source; **PBP score
reconciliation** (running score vs final, FT sequences, technicals, OREB chains, OT);
**lineup possession reconciliation** (not just boxscore minutes — RAPM needs correct score
changes, substitutions, and stint boundaries); odds freshness & stale-book detection;
injury/news feed freshness; expansion-team identity mapping; postponements & changed tip
times (tip time known-at-capture is stored with every odds snapshot).

## Phase 0.5 — Point-in-time & evaluation certification (before any channel testing)

The **evaluation harness, in code, before any model is rebuilt** (`evalharness/`):
- Outer walk-forward evaluation; inner walk-forward tuning strictly inside the training
  period; a separate calibration window disjoint from model fitting; a **locked final holdout
  touched once** (declared in the registry the day it is first used).
- **Experiment registry:** every experiment registered (id, hypothesis, features, gate
  thresholds) in `experiments/registry.jsonl` and committed **before** execution. Unregistered
  results are void.
- **Paired, game-level residual comparison** against the incumbent; bootstrap confidence
  intervals **clustered by game date** (and by team as sensitivity).
- **Minimum practical improvement** preregistered per experiment; automatic rejection if
  prediction coverage materially declines.
- **Frozen reference baselines** pinned permanently in the harness: home-advantage-only
  (11.22), raw-trend channel sum (10.53), incumbent structural chains (9.54), minutes
  carry-forward (5.42) and expanding-mean (5.12), and "market at cutoff" rows.

### Standard promotion gate (template — thresholds preregistered per experiment)
Promote a challenger only when ALL hold on pooled walk-forward results:
1. Pooled MAE (or the registered primary metric) improves by ≥ the preregistered meaningful
   amount (default 0.10 points for game-margin models);
2. The 90% paired-bootstrap CI excludes degradation worse than 0.05;
3. **Non-inferior in every individual season** (no season degrades by more than 0.15);
4. The **final joint forecast** (home score, away score, margin, total) does not degrade;
5. Coverage and operational reliability maintained.
Never "must win all three seasons" (one bad season vetoing a real gain) and never "three tiny
point wins" (promoting noise).

### The four evaluation regimes (every registered experiment declares one)

**A. Historical core evaluation** — full walk-forward legitimacy: team channels, shifted
trends, zones, RAPM, refs-at-cutoff, boxscore-derived rotation features. Certifies the
no-news basketball model. This is the only regime that proves anything on its own.

**B. Audited historical availability subset** — injury/news records used ONLY where
contemporary publication times are trustworthy. Every B result reports: games covered, teams
covered, source coverage, time-of-day coverage, and whether missingness is systematic.
Results apply to the covered subset, nothing wider.

**C. Oracle sensitivity analysis** — brackets W1's potential value without claiming to
isolate it. Four runs: (1) no availability info; (2) reconstructed availability (regime-B
data); (3) **pregame oracle** = final active/DNP status + confirmed starters — the
meaningful upper bound for perfect pregame availability knowledge; (4) **omniscient minutes
oracle** = actual realized minutes — a diagnostic ceiling ONLY, contaminated by in-game
information nobody had at tip (foul trouble, in-game injury, overtime, blowouts, coaching
reactions). Actual minutes are never described as what perfect news extraction could achieve.

**D. Prospective full-system evaluation** — the only regime that validates the news-aware
system. **Two distinct dates, never conflated:** *capture start* (2026-07-30 — point-in-time
raw data begins accumulating; creates a replay corpus, proves nothing) and *prospective
evaluation start* (unset — begins only when a FROZEN model version issues timestamped,
immutably logged predictions before each game). Tuning on captured months and then
"replaying" them is retrospective development, not prospective validation. At every cutoff
the logger records: model/version hash, data snapshot hash, W1 extraction, core-only
prediction, core+W1 prediction, available market line and price, predicted close, intended
bet decision, paper stake. Core-only and core+W1 run simultaneously on the same future games
— the cleanest measurement of W1's incremental contribution.

**Verdict readiness is sample-defined, not calendar-defined.** No "decision-grade by season
X" promises: the real sample size is the number of independent eligible betting decisions,
not games. Preregister minimum prediction count, minimum bet count, confidence-interval
width requirement, and calibration threshold; the verdict is ready when they are met.

### Metrics (probability quality is first-class)
- Score/margin/total MAE and RMSE; pinball loss on forecast quantiles; CRPS (distributional);
  cover-probability Brier; log loss; reliability/calibration plots.
- Betting-facing: ROI after vig; CLV **by decision time**; max drawdown; bankroll volatility;
  bet count / effective sample size.
- Calibration method is an open competition on past data only: Platt/sigmoid vs isotonic vs
  hierarchical — isotonic is NOT the presumed winner at WNBA sample sizes.

### Leaderboards (replaces the single MAE leaderboard)
`leaderboards/FORECASTING.md` (score/margin/total point error, by decision time) ·
`leaderboards/PROBABILISTIC.md` (CRPS, log loss, Brier, calibration) ·
`leaderboards/MARKET.md` (close-prediction error, line-path models) ·
`leaderboards/BETTING.md` (simulated ROI, CLV, drawdown — decision policies).
Market rows appear as benchmarks in all four. Quarantined experiments post win or lose.

## Phase 1 — Uniform master rebuild & channel re-validation

1. V2/V3 normalizer (in flight tonight) → uniform masters with provenance fields → row-level
   diff vs the July-15 Drive masters; unexplained mismatch stops the line.
2. **Channel re-validation under the harness** with repaired 2023: walk-forward 2024/2025/2026
   under the standard gate (pooled + non-inferiority — not all-seasons-must-win).
3. **Joint-forecast coherence:** channels are promoted only as part of a coherent joint
   forecast. Track the **residual covariance matrix between channels** — a channel that
   improves alone but breaks error cancellation in the sum is rejected by gate #4.
   "Structural sum" means a coherent joint forecast, not an arithmetic sum of independently
   optimized parts.

## Phase 2 — Player layer

### 2a. W1 — News → Availability (build-in, highest priority)
- **LLM = auditable extraction layer only** — it never invents minutes. Extraction schema:
  exact quoted evidence, source tier (player/coach/team/league/reporter), publication time,
  body part, designation, reported limitation.
- **Three separate targets:** `P(active)` (Brier, log loss) · `E[minutes | active]` (MAE) ·
  uncertainty interval on conditional minutes. Combined `E[min] = P(active) × E[min|active]`
  evaluated separately, then downstream game-model impact (gate #4).
- **Point-in-time honesty:** the historical injury archive records what was *eventually*
  known, not what was knowable at a historical cutoff. W1 backtests are regime-B only
  (trustworthy contemporary timestamps); the live capture (designation revisions preserved,
  hourly on game days) is the gold-standard training set as it accumulates.
- **W1 is graded against:** subsequent official active/DNP status; confirmed starters;
  minutes conditional on playing; improvement of frozen pregame game forecasts; improvement
  of betting decisions at the same timestamp. **Line movement is a secondary relevance
  signal only** — movement also reflects price discovery, sharp action, book copying, model
  corrections, and liability management, so it can suggest W1 is looking at real information
  but can never grade whether an extraction was correct.
- Gate baseline: shifted minutes-EWMA × active-flag (5.42 / 5.12 floors), under the harness,
  regime declared per experiment (A for past-games-only features; B/C/D as defined above).

### 2b. RAPM (build-in; before W2 per revised critical path)
- Inputs ready: 116,317 validated stints. Prerequisite: possession attribution passes the
  Phase-0 possession reconciliation (score changes, FT sequences, OREB chains, OT).
- **Gates:** predictive stint error on future games; future on/off & lineup performance
  prediction; year-over-year stability; stability across reasonable ridge penalties;
  sensitivity to garbage-time/low-leverage possessions; sane replacement-level behavior for
  rookies and low-minute players. "Known stars rank sensibly" is a **smoke test for broken
  data only — never a promotion criterion** (reputation hand-tuning risk).

### 2c. W2 — Location-and-context expected points (build-in)
- Renamed from "shot quality": without defender distance/contest/pass/movement data this is
  **location-based** xP, and claims stay sized accordingly.
- Five separated components: shot-location tendency · location-based conversion expectation ·
  shooter over/under-performance vs location xP · opponent allowed-location distribution ·
  opponent conversion-allowed (shrunken).
- **Heavy empirical-Bayes/hierarchical shrinkage** on player-zone cells; player maps activate
  only at sufficient attempts, else back off to team/position/league priors.
- Gates: per-channel improvement AND joint-forecast improvement (residual-covariance rule).

### W3 — NBA transfer learning (QUARANTINED; after RAPM exists)
Unchanged: must beat WNBA-only equivalents under the harness; result posted win or lose.
John's documented concern (playstyle drift, e.g. interior dynamics) stands.

### W4 — Referee model (cheap isolated sidecar)
- **Assignments are timestamped data:** usable only if public before the forecast cutoff.
  Historical officials crawl (queued) supplies priors; a daily assignments capture feeds live
  point-in-time features.
- Partial pooling across officials and seasons; three-official crew aggregation.
- Evaluate: foul rate, shooting-foul rate, FTA per relevant attempt, home/away differential,
  pace effects. Stays isolated until it passes both FT-channel and joint gates — small effect
  expected; never auto-included.

### W6 — Playing-through-it detector (experiment queue)
- Precursors are rare → raw accuracy is meaningless. Registered metrics: precision & recall,
  **false alerts per 100 player-games**, median lead time (days before documented news),
  incremental value beyond schedule/rest/minutes baselines, minutes-model improvement,
  game-model improvement. Must work **prospectively** before promotion — a retrospective
  correlation is a leaderboard footnote, not a feature.

## Phase 3 — Market model & betting system

### W5 — Market / closing-line model (separate system #2)
- **Capture > modeling for now**: line-path modeling waits for Phase 3, but the capture is
  immediate (hourly as of tonight) because line paths cannot be recreated. Stored per
  snapshot: book, spread/total, price/juice, timestamp, **tip time known at capture**,
  open/current/final-available-pre-tip, suspensions & reopenings, stale-line status, best
  executable vs consensus price (derivable from per-book rows; raw JSON always archived).
- **Cadence correction (2026-07-30 finding):** the old master on disk holds a **single
  T≈−64min snapshot per (game, book)** — a near-tip benchmark line for 813 games 2022–25,
  not line paths (the handoff's "hourly snapshots" described the upstream archive). The raw
  multi-snapshot JSONs exist in Drive `historical_odds/` — recovery = John downloads the
  folder into data/drive_masters/. New-era line-path research runs on the 2/day backfill and
  the hourly live capture. First registered negative result: line-path-only ridge (current
  line, hours-to-tip, movement) scores 1.007 MAE vs 0.980 for "close = current line" — the
  path to the W5 gate is exogenous W1 news features plus true near-tip lines (hourly capture
  now provides them); findings that don't transfer across cadences are labeled as such.

### Betting decision layer (separate system #3)
- **Three decision policies compared under the harness — none presumed:**
  (1) basketball model vs current market; (2) basketball model vs predicted close;
  (3) basketball model blended with current market.
- **Real-money gate (replaces "beat avg bookie MAE + paper CLV"):** on a **preregistered
  prospective sample**: calibrated edge probabilities (conditional edge calibration), positive
  CLV after vig-aware normalization, acceptable drawdown, adequate bet count, and performance
  **not explained by one period/team/book**. Global bookie MAE is diagnostic, never a
  necessary condition — a model can lose globally and win in a calibrated subset.
- **Kelly with explicit uncertainty discounting:** conservative probability shrinkage toward
  the market; uncertainty haircut on estimated edge; max stake per game; max correlated
  exposure per slate; daily/weekly loss limits; no-bet zone around zero edge; overconfidence
  sensitivity tests. Fractional Kelly alone is not a risk system.

---

## Immediate parallel captures (cannot be recreated later — running/starting now)
- Hourly odds snapshots 10:00–23:00 (paid month; free-tier fallback design: 2-hourly on game
  days only, fits 500 credits/mo)
- Injury designation revisions, hourly on game days (raw PDF always archived)
- News raw-text capture (feed inventory in flight tonight)
- Referee assignments daily capture (to build once assignments-page format is pinned)
- Exact forecast-time feature snapshots (begins when daily forecasts begin)

## Explicitly rejected (unchanged)
Social sentiment · streak/momentum narratives · broadcast-video CV (parked moonshot) ·
astrology.

## Revised critical path
Continuous certification → point-in-time prediction contract → **evaluation/calibration
harness** → frozen simple baselines → uniform master rebuild → channel revalidation → W1
extraction + conditional-minutes model → RAPM → W2 zones → coherent full-model rebuild → W4
referee experiment → calibrated outcome distributions → betting simulator → W5 market model →
shadow/paper trading → risk-controlled sizing.
