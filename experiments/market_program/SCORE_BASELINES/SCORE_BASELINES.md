# SCORE_BASELINES — pace × efficiency composite baselines for total, margin, win probability

**Node:** `experiments/market_program/SCORE_BASELINES/` · **Mandate:** D043 item 1 (IMMEDIATE, no gate)
**Authorities (binding):** `D043_CYCLE2_SCORE_AND_EFFICIENCY`, `D036_SCOREBOARD_MEASUREMENT_SEMANTICS`
(`experiments/player_program/orchestration/DECISION_LEDGER.jsonl`).
**Evidence class:** `COMPOSITE_BASELINE` — **NAIVE_BASELINE semantics per D036 point 6**: an untuned,
strictly-lagged floor from owned data. Nothing here is a fitted challenger, predictive evidence for
any model, or a timing/CLV claim. This node never touches `SEALED_RESULTS`. No git, no network,
no subagents.

## The headline, plainly

On the **matched universe** (BOOKIE_BASELINE's frozen 2022–2026 archive join, LATE snapshot,
cross-book consensus, paired game-for-game, game-date-clustered 95% CIs):

| Metric | Composite | Market consensus | Gap (composite − market) | 95% CI | n pairs |
|---|---|---|---|---|---|
| Margin (spread) MAE | **10.48** | 9.68 | **+0.80 pts** | [+0.51, +1.08] | 1,059 |
| Total MAE | **14.12** | 13.74 | **+0.38 pts** | [+0.17, +0.59] | 1,052 |
| Win-prob Brier | **0.2182** | 0.2014 | **+0.0168** | [+0.0097, +0.0239] | 1,058 |
| Win-prob log loss | **0.6256** | 0.5878 | **+0.0378** | [+0.0217, +0.0539] | 1,058 |

**The market beats the composite on every score-family metric, and every gap is statistically
significant (no CI includes zero). But the gaps are small in absolute terms:** a ten-game trailing
pace window times a span-10 points-per-possession EWMA — with no home-court term, no injuries, no
rest, no rosters — lands within **0.4 points of the market on totals (2.8% worse), 0.8 points on
margin (8.2% worse), and 0.017 Brier on win probability (8.3% worse)**. That is the floor every
future score-family model must clear; the distance from this floor to the market bars is the entire
room the modeling program has to work in on these targets.

Context bars quoted in D043 (spread 9.70 / total 13.74 / Brier 0.202) are BOOKIE_BASELINE's pooled
LATE cross-book numbers on its full matched archive; the verdict rows above are **paired** on the
identical game set for both sides, which is the only comparison this node treats as a verdict.
**No unmatched-universe comparison in this report is a verdict** — the full-universe tables below
are coverage-different and are context only.

## Construction (all inputs strictly lagged — every ingredient comes from games on strictly earlier calendar dates)

**(a) Pace ingredient — the VERIFIED incumbent, consumed as-is.**
`projected_team_off_possessions` from
`experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet` — the
receipted trailing-window champion (WINDOW_K=10 same-season window mean, prior-season window then
strictly-lagged league mean as receipted fallbacks) that survived the P40 challenger sweep (D042).
It is a game-level, regulation-equivalent offensive-possession count, identical on both team rows.
**Coverage: 2,982 / 2,990 team-game rows (99.73%); 1,491 / 1,495 games.** The 4 uncovered games
(8 rows, first game date of 2021) have `pace_source=unresolved_no_prior_games` with **zero** prior
games anywhere — no EWMA reconstruction is possible for them (there is nothing to reconstruct
from), so they are excluded and counted, never imputed. Source mix on the covered rows:
`team_window_same_season` 2,762 · `team_window_prior_season` 183 · `league_prior_all` 37.

**(b) Efficiency ingredients — one picked convention, documented, not tuned.**
Strictly-lagged EWMA of points-per-possession scored (offense) and allowed (defense) per team.
`ppp = box-score points / raw offensive-possession count` from
`possessions_v2/possessions_raw_v2.parquet` — the same possession stream the pace prior was built
from, so pace × ppp is scale-consistent. Both numerator and denominator include OT, so ppp is a
true rate. **The picked convention is the simple span: EWMA span 10 (α = 2/11), history continuous
across seasons, minimum 3 strictly-prior games** (mirrors the incumbent's WINDOW_K=10 /
MIN_HISTORY_M=3 flavour). D036/D043 offered K=200-style shrinkage *or* a simple span; the simple
span was picked, no shrinkage, and the span was **not** searched — this is a baseline, not a model.
Cross-season continuity is a deliberate, documented simplification versus the incumbent pace
prior's same-season-first windows.

**(c) Composite.** predicted team score = pace × (0.5·own-offense EWMA + 0.5·opponent-defense
EWMA); predicted total = sum of both sides; predicted margin = home − away. **There is no
home-court-advantage term by construction** — the resulting negative margin bias (pooled −1.77) is
reported, not hidden. Predicted scores are regulation-equivalent while realized totals include OT
points, contributing a small shared negative total bias.

**(d) Win probability.** `p(home) = logistic(intercept + slope × predicted margin)`, calibrated
**only on strictly-prior seasons, walk-forward, never pooled** (2022 trained on 2021 alone; 2026
trained on 2021–2025; coefficients per season in `score_baselines.json`). The logistic's intercept
absorbs home-court advantage out of sample. **2021 has no prior season and gets no win
probability** — a stated exclusion (188 composite games), not a silent drop.

### Cold starts and exclusions (counted, never silent)

| Method | Exclusion | n games |
|---|---|---|
| composite | `PACE_UNRESOLVED_NO_PRIOR_GAMES` (first 2021 date, zero history) | 4 |
| composite | `EFF_HISTORY_LT_3_PRIOR_GAMES` (either team; season openers 2021 + expansion teams GSV/PDX/TOR) | 26 |
| composite | win prob only: no prior-season calibration data (all of 2021) | 188 |
| league_average | `NO_PRIOR_LEAGUE_GAMES` (first game date in the data) | 4 |
| team_scoring_avg | `NO_SAME_SEASON_PRIOR_GAME_EITHER_TEAM` (every team's season opener) | 39 |

Team-game rows missing from the possession stream: 0.

## Full-universe results — owned gamelogs 2021–2026, walk-forward, per season + pooled

Every cell: game-date-clustered 95% CIs in `score_baselines.json`; MAE CIs shown inline here.
2026 is a partial season (through 2026-07-31). Universe = each method's covered games (see
exclusions above) — these tables are **not** market-comparable and are never quoted as verdicts.

### composite_pace_x_eff_v1 (the D043 composite — leaderboard current-best rows for the score family)

| Season | n | Dates | Total MAE [CI] | Total RMSE | Total bias | Margin MAE [CI] | Margin RMSE | Margin bias | Brier [CI] | Log loss |
|---|---|---|---|---|---|---|---|---|---|---|
| POOLED | 1,465 | 2021-05-21..2026-07-31 | 13.82 [13.26, 14.38] | 17.61 | −1.32 | 10.34 [9.93, 10.75] | 12.99 | −1.77 | 0.2181 [0.2097, 0.2266] (n=1,277) | 0.6252 |
| 2021 | 188 | 05-21..10-17 | 12.73 [11.32, 14.14] | 16.21 | −1.74 | 10.14 [9.01, 11.27] | 12.82 | −1.04 | — (no prior season) | — |
| 2022 | 239 | 05-06..09-18 | 13.43 [12.07, 14.79] | 17.56 | −1.53 | 10.30 [9.29, 11.30] | 12.75 | −1.22 | 0.2235 [0.2046, 0.2424] | 0.6367 |
| 2023 | 260 | 05-19..10-18 | 13.95 [12.68, 15.22] | 17.51 | −0.46 | 10.49 [9.54, 11.43] | 13.10 | −2.28 | 0.2145 [0.1985, 0.2305] | 0.6170 |
| 2024 | 262 | 05-14..10-20 | 12.61 [11.37, 13.84] | 16.26 | −0.35 | 9.34 [8.49, 10.18] | 11.43 | −1.05 | 0.2128 [0.1936, 0.2321] | 0.6146 |
| 2025 | 307 | 05-16..10-10 | 13.56 [12.41, 14.71] | 16.80 | −0.57 | 11.12 [10.16, 12.09] | 14.08 | −2.80 | 0.2184 [0.1995, 0.2372] | 0.6243 |
| 2026 | 209 | 05-08..07-31 | 16.98 [15.25, 18.71] | 21.40 | −4.08 | 10.47 [9.34, 11.61] | 13.43 | −1.82 | 0.2229 [0.2010, 0.2448] | 0.6368 |

The 2026 total bias (−4.08) mirrors BOOKIE_BASELINE's independent observation that 2026 totals ran
well above the market's number too (market total bias ≈ −3.6 that season): actual 2026 scoring is
high relative to *any* trailing predictor, market included. Reported, not explained (same stance as
BOOKIE_BASELINE).

The pooled win-prob calibration (10-bin, in `score_baselines.json`) tracks the diagonal within
about ±0.05 for every bin with n ≥ 75; the walk-forward logistic is honestly calibrated out of
sample.

### league_average_v1 (strictly-lagged expanding league means; margin mean = home-court advantage; win prob = lagged home win rate)

| Season | n | Total MAE [CI] | Total RMSE | Total bias | Margin MAE [CI] | Margin RMSE | Margin bias | Brier |
|---|---|---|---|---|---|---|---|---|
| POOLED | 1,491 | 14.39 [13.80, 14.98] | 18.41 | −1.85 | 11.41 [10.99, 11.82] | 14.04 | −0.54 | 0.2492 |
| 2021 | 205 | 13.55 [12.16, 14.93] | 17.08 | +0.83 | 11.38 [10.25, 12.52] | 14.26 | −0.66 | 0.2528 |
| 2022 | 239 | 13.48 [11.98, 14.99] | 17.94 | −2.04 | 11.31 [10.29, 12.34] | 13.79 | −0.45 | 0.2491 |
| 2023 | 260 | 14.24 [13.11, 15.37] | 17.56 | −1.82 | 11.79 [10.86, 12.72] | 14.19 | −1.00 | 0.2495 |
| 2024 | 262 | 13.38 [12.11, 14.66] | 17.14 | +0.53 | 10.56 [9.59, 11.54] | 12.69 | +0.17 | 0.2482 |
| 2025 | 310 | 13.67 [12.58, 14.75] | 16.84 | +0.27 | 11.98 [10.98, 12.98] | 14.98 | −1.19 | 0.2465 |
| 2026 | 215 | 18.66 [16.62, 20.69] | 23.97 | −10.20 | 11.28 [10.24, 12.32] | 14.11 | +0.07 | 0.2503 |

### team_scoring_avg_v1 (season-to-date points scored/allowed averages, NO pace decomposition; same walk-forward logistic for win prob)

| Season | n | Total MAE [CI] | Total RMSE | Total bias | Margin MAE [CI] | Margin RMSE | Margin bias | Brier |
|---|---|---|---|---|---|---|---|---|
| POOLED | 1,456 | 13.94 [13.38, 14.50] | 17.73 | −0.68 | 10.28 [9.87, 10.68] | 12.89 | −1.77 | 0.2156 (n=1,253) |
| 2021 | 203 | 13.18 [11.83, 14.54] | 16.53 | +0.93 | 10.42 [9.28, 11.55] | 13.22 | −0.70 | — |
| 2022 | 233 | 13.50 [12.07, 14.92] | 17.84 | −1.18 | 10.22 [9.19, 11.24] | 12.72 | −1.45 | 0.2168 |
| 2023 | 254 | 14.08 [12.84, 15.33] | 17.52 | −1.35 | 10.31 [9.41, 11.21] | 12.73 | −2.35 | 0.2086 |
| 2024 | 256 | 12.79 [11.54, 14.05] | 16.48 | −0.14 | 9.21 [8.36, 10.07] | 11.29 | −0.95 | 0.2065 |
| 2025 | 303 | 13.46 [12.36, 14.55] | 16.65 | −0.28 | 11.04 [10.14, 11.93] | 13.90 | −2.54 | 0.2239 |
| 2026 | 207 | 17.15 [15.37, 18.93] | 21.60 | −2.16 | 10.39 [9.20, 11.57] | 13.23 | −2.34 | 0.2216 |

**An honest and slightly uncomfortable observation:** at this untuned-baseline level, the pace
decomposition buys little over plain season-to-date scoring averages — pooled margin MAE 10.34 vs
10.28, total MAE 13.82 vs 13.94, Brier 0.2181 vs 0.2156, all well inside each other's CIs (no
paired test between the two baselines was run; the pooled win-prob universes also differ slightly,
1,277 vs 1,253 games). The composite's value is structural — it decomposes score into the verified
pace ingredient and an efficiency residual, which is exactly the decomposition the F12/F13 Cycle-2
designs attack — not a measured accuracy edge over the simpler average at baseline strength. Both
sets of rows go to the leaderboard; the composite rows are the designated current-best-estimate
rows for the score family per D043, with this observation attached.

## Market comparison — matched universe ONLY

**Universe:** BOOKIE_BASELINE's frozen join (reused read-only, never reimplemented: same
name→abbreviation map, same ET-date estimate, same exact-date-then-unambiguous-±1-day rule, same
in-play exclusion; M11's frozen `multiplicative_proportional` de-vig for the consensus) of the
2022–2026 T1 odds archive to owned outcomes. **LATE snapshot class, cross_book variant.** 1,070
matched games carry a LATE quote; 1,061 of those also have composite coverage (the 9 dropped are
early-season games inside the composite's cold-start exclusions — counted, per-metric pair counts
in the table above and in `score_baselines.json`). Both sides of every paired difference are
computed on the identical games; deltas are per-game paired and game-date-clustered per D036
point 7. D036 provenance: `provenance_class: T1_VENDOR_ASSERTED`,
`vendor_ts_semantics: vendor_asserted_unwitnessed`.

The T1 timing caveat, **verbatim** (frozen text; sha256
`93a816cc9357af8d0a09da60695eee60e6921b1cbf1fbcb2b7c8b125216e21f7`, verified by
`TESTS.py::output_caveat_sha_matches_bookie_frozen_constant`):

> "This snapshot's timestamp is vendor-asserted and unwitnessed (tier T1:
> THIRD_PARTY_CONTEMPORANEOUS, per MARKET_PROGRAM_CONTRACT.md section 4.3). It is drawn from a
> third-party historical-odds archive retrieved on 2026-08-06, labelled EARLY (vendor-asserted
> ~16:00Z request) or LATE (vendor-asserted ~23:30Z request) relative to the archive's own request
> day, not from our own real-time capture. LATE is closer to commence than EARLY, but neither is a
> witnessed closing line, and the true hours-to-commence at capture is not independently verified.
> No timing, latency, reaction, or CLV inference may be drawn from this snapshot; it supports
> calibration-against-realized-outcomes only, at an unknown-but-bounded-pregame instant."

Full paired table (deltas = composite − market; positive = market better; MSE rows support RMSE
reasoning without a nonlinear transform of the paired statistic):

| Metric | Composite | Market | Paired Δ | 95% CI (clustered) | n pairs | Date range |
|---|---|---|---|---|---|---|
| Margin MAE | 10.478 | 9.681 | +0.797 | [+0.514, +1.080] | 1,059 | 2022-05-06..2026-07-31 |
| Margin MSE | 172.45 | 151.78 | +20.67 | [+12.83, +28.51] | 1,059 | 〃 |
| Total MAE | 14.118 | 13.735 | +0.383 | [+0.171, +0.594] | 1,052 | 〃 |
| Total MSE | 323.58 | 305.38 | +18.20 | [+9.92, +26.48] | 1,052 | 〃 |
| Brier | 0.2182 | 0.2014 | +0.0168 | [+0.0097, +0.0239] | 1,058 | 〃 |
| Log loss | 0.6256 | 0.5878 | +0.0378 | [+0.0217, +0.0539] | 1,058 | 〃 |

## What this node does NOT establish

* Any betting edge, executability, or timing claim — the T1 caveat bounds the market side, and a
  baseline losing to the market by +0.38/+0.80/+0.017 with tight CIs is evidence of the market's
  strength, not of any exploitable pocket.
* Whether the composite's remaining gap comes from information (injuries, rosters, rest, travel)
  or from estimator quality — that decomposition is exactly the F12/F13 Cycle-2 mandate and is not
  prejudged here.
* Why 2026 scoring runs above every trailing predictor including the market — reported, not
  explained (consistent with BOOKIE_BASELINE's stance).
* Any tuning claim: the span-10/min-3/0.5-blend conventions were picked once and documented, never
  searched. A tuned variant would be a challenger and belongs to the preregistered cycle, not here.

## Reproducing

```
python experiments/market_program/SCORE_BASELINES/TESTS.py                  # 43 known-answer fixtures
python experiments/market_program/SCORE_BASELINES/build_score_baselines.py  # full measurement pass
```

Outputs: `score_baselines.json` (all methods × seasons + pooled, full CI/calibration detail, D036
provenance blocks per row, input sha256s, producer self-hash), `score_baseline_rows.parquet`
(per-game predictions for leaderboard reuse), `market_paired_rows.parquet` (the paired
matched-universe rows). Re-runs are deterministic (verified: two consecutive builds produced
identical metrics).
