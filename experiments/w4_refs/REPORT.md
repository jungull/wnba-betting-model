# W4 — Referee FTA-Prior Crew Factor on the FT Channel (FAIL)

**Point-in-time caveat (registered):** this backtest uses the **actual** game crew as a proxy for the pregame-announced crew. Historical announcement pages were not archived; officials are posted ~9:00am ET on game day and late swaps are rare but **unquantified here**. Live deployment uses the daily assignments capture (`ref_assignments_capture_daily.py`), which *is* point-in-time. This proxy assumption must be stated on every report of this result.

*2026-07-30T21:28:40+00:00 · registered experiment `w4_ref_fta_priors_v1` (registered 2026-07-30T21:05:19.768612+00:00,
regime A, primary metric `ft_channel_mae`, incumbent
`chanreval_structural_ft_chain`) · run mode **REAL** — recorded on the real ledger
· code `w4_refs.py` (repo root) · data `data/officials_master.csv`,
`data/masters/master_team.parquet`, incumbent artifacts in `experiments/channel_reval/`.*

## Verdict

**FAIL — clean null.** The crew FTA-prior multiplier
does not move the FT channel:
challenger FT MAE **4.3053** vs incumbent **4.3044**
(pooled improvement **-0.0009**, 90% date-clustered bootstrap CI
[-0.0039, +0.0018], 250 date clusters,
1346 team-game rows on the registered universe of
673 games). Tuned pooling constant K* = 512
(train-only) — the tuner chose heavy shrinkage,
crew factors hug 1.0 (test-universe mean 1.0018, sd 0.0036), and the
registered [0.92, 1.08] bound activated on 0
of 673 test games. The registered expectation was a small effect
("cheap isolated sidecar — never auto-included"); the ROADMAP W4 design keeps this
isolated until it passes both FT-channel and joint gates, which it does not.

| Gate | Result |
|---|---|
| Pooled improvement >= 0.10 | FAIL |
| 90% date-clustered CI excludes harm > 0.05 | PASS |
| No season worse than -0.15 | PASS |
| Joint forecast non-degrading (substitution) | PASS |
| Coverage maintained | PASS |

Failed gates: gate1_pooled_improvement.

## Primary — FT channel MAE (challenger vs incumbent, walk-forward)

Units are team-game FT-channel rows (2 per game, equal weight — pooled MAE and the
date-clustered CI are identical under per-game averaging; n counts rows).

| Season | n rows | Challenger | Incumbent | delta (improvement) |
|---|---|---|---|---|
| 2024 | 458 | 4.0262 | 4.0285 | +0.0023 |
| 2025 | 552 | 4.2915 | 4.2887 | -0.0028 |
| 2026 | 336 | 4.7085 | 4.7063 | -0.0022 |
| **pooled** | 1346 | **4.3053** | **4.3044** | **-0.0009** |

Team-clustered sensitivity CI: [-0.0028, +0.0010]
(15 franchise clusters).

## The challenger

`prior_r(t)` = shrunken mean of (game total FTA / walk-forward league mean FTA) over
referee r's games strictly before t; partial pooling `n/(n+K)` toward 1.0, K tuned
train-only; crew factor = mean over the game's listed officials, clipped to
[0.92, 1.08] (registered, fixed). Challenger FT channel = incumbent structural
FT chain x crew factor, both teams symmetrically. League mean FTA is an expanding mean
over strictly earlier dates (audited below) — never a global constant.

## K tuning curve (3 inner walk-forward folds strictly inside 2021-2023)

Incumbent (no crew factor) inner-fold mean MAE: **4.190160**.

| K | fold1 | fold2 | fold3 | mean | delta vs incumbent |
|---|---|---|---|---|---|
| 1 | 4.0378 | 4.2559 | 4.3441 | 4.212607 | -0.022447 |
| 2 | 4.0420 | 4.2526 | 4.3365 | 4.210359 | -0.020199 |
| 4 | 4.0441 | 4.2477 | 4.3252 | 4.205690 | -0.015530 |
| 8 | 4.0463 | 4.2434 | 4.3102 | 4.199991 | -0.009831 |
| 16 | 4.0501 | 4.2411 | 4.2948 | 4.195327 | -0.005167 |
| 32 | 4.0544 | 4.2395 | 4.2814 | 4.191761 | -0.001601 |
| 64 | 4.0592 | 4.2398 | 4.2721 | 4.190352 | -0.000192 |
| 128 | 4.0643 | 4.2403 | 4.2658 | 4.190126 | +0.000034 |
| 256 | 4.0679 | 4.2407 | 4.2615 | 4.190005 | +0.000155 |
| 512 | 4.0700 | 4.2409 | 4.2589 | 4.189931 | +0.000229 **<- K*** |
| 1024 | 4.0713 | 4.2411 | 4.2576 | 4.190001 | +0.000159 |
| 2048 | 4.0720 | 4.2412 | 4.2570 | 4.190080 | +0.000080 |
| 4096 | 4.0724 | 4.2413 | 4.2567 | 4.190120 | +0.000040 |

The curve improves monotonically toward heavy pooling and is essentially flat past K=64 (full range 0.0227 MAE points); the shallow optimum at K*=512 beats the no-crew incumbent by only +0.000229 FT-MAE points on the inner folds. 2021-2023 shows no exploitable referee FTA signal at face value, so the train-only tuner compresses the crew factor toward 1.0.

## Crew factor distribution (at K* = 512)

| Scope | n | mean | sd | min | p05 | p50 | p95 | max | at lower bound | at upper bound |
|---|---|---|---|---|---|---|---|---|---|---|
| all 1,489 games | 1489 | 1.0007 | 0.0031 | 0.9908 | 0.9963 | 1.0003 | 1.0063 | 1.0122 | 0 | 0 |
| test universe (673) | 673 | 1.0018 | 0.0036 | 0.9908 | 0.9962 | 1.0018 | 1.0079 | 1.0122 | 0 | 0 |

Bound-activation rate: 0.00% of all games,
0.00% of the test universe. Unclipped crew-prior mean
1.0007 over all games — the ratio construction runs slightly above 1
because league FTA drifted upward across 2021-2026 while the expanding league mean lags;
the tuned shrinkage compresses exactly that.

## Secondaries (recorded, not gated) — substitution + train-only recalibration

Challenger FT channel substituted into both teams' structural sums; margin/home/away
calibrations refit on 2021-2023 eligible games only (n = 610); scored on the 673.

| Component | Challenger MAE | Incumbent MAE | delta (improvement) |
|---|---|---|---|
| home_score | 8.7884 | 8.7928 | +0.0043 |
| away_score | 8.6129 | 8.6163 | +0.0034 |
| margin | 10.0862 | 10.0860 | -0.0002 |
| total | 14.2139 | 14.2236 | +0.0097 |

Joint check (gate-4 style, tolerance 0.05): no component degrades beyond tolerance.
Game-total MAE by season (challenger / incumbent): 2024: 13.065 / 13.068 · 2025: 13.359 / 13.364 · 2026: 17.185 / 17.212.
Refs plausibly move totals more than margins; at K* = 512 the substitution
moves neither materially.

## Data verification

- `officials_master.csv`: 1489 games (= the full master universe), 63
  distinct officials, 0 duplicate (game, official) rows, 0 games missing officials,
  0 official rows for unknown games. Joined to `master_team.parquet` on the repo's
  10-digit string `game_id`.
- **Deviation from the registered "3 refs/game":** 1406 games list
  exactly 3 officials; **83 playoff games list 4** (the boxscore
  officials table includes the alternate for playoff games; the source carries no role
  labels, and listing order is not a documented contract). Primary uses **all listed
  officials**; a first-3-only sensitivity is reported below. 39
  of the 673 universe games list 4 officials.
- Game FTA from `data/masters/master_team.parquet` (2 rows per game, summed), cross-checked
  exactly (max |diff| = 0) against `channel_base_v2.csv`.
- 4 games on the dataset's first date
  (2021-05-14) have no league baseline -> no ratio; they are excluded
  from every referee's history (no information is invented) but still receive crew factors.

## Incumbent reproduction (certified before anything else ran)

Rebuilt the chanreval pipeline via `experiments/channel_reval/run_reval.py`'s own
functions (alphas from `run_summary.json`: ft = 0.1). Hard asserts, all passed:

- FT channel table matches `channel_results_v2.csv` on n / raw MAE / structural MAE in
  all 4 scopes exactly (pooled: n = 1362,
  structural 4.304178);
- game-level calibrated predictions match `predictions_v2.csv` across 11 numeric columns
  x 673 games, max |diff| = 2.84e-14.

The incumbent's per-team-game FT predictions used here are therefore bit-identical to the
ledgered chanreval run. (Incumbent pooled FT MAE on the 1,346-row universe is
4.3044 vs 4.3042 on the
channel table's 1,362 rows — the table additionally includes 16 rows from games whose
*opponent* was under the 5-prior-game floor; the registered universe is the 673 games.)

## Leakage audits (constitution rule 1 — run before believing)

1. **Prior walk-forward audit (truncate + recompute):** 48 sampled
   (ref, date) pairs across all seasons; each prior rebuilt from raw officials + master
   FTA by an independent loop-based recompute truncated strictly before t.
   **0 mismatches, max |diff| = 2.22e-16**. Including
   date-t games changes the value in 48/48
   pairs — the truncation is real, no game at/after t enters any prior.
2. **League-mean walk-forward audit:** 12 sampled dates recomputed
   strictly-before by brute force: 0 mismatches
   (max |diff| = 0); 12/12
   sampled dates differ from the global mean (it is expanding, not global), and the
   first date's league mean is NaN by construction.
3. **K tuned strictly inside 2021-2023** via `evalharness.inner_tuning_splits` (leakage-
   checked fold construction); test seasons never touched tuning. The curve is above.
4. Universe / truth columns are the chanreval artifacts' own, reproduced bit-identically
   (see reproduction section); coverage is identical for both models by construction
   (crew factors exist for all 1,489 games).

## Sensitivity — first-3 listed officials only

Priors and crew factors rebuilt using only each game's first 3 listed officials
(same K* = 512): pooled challenger FT MAE 4.3054
(vs 4.3053 primary; delta vs incumbent -0.0010
vs -0.0009 primary); crew factors differ from primary on
83 of 1,489 games (max |diff| 0.0039).
The 4-official ambiguity does not change the conclusion.

## Files

- `w4_refs.py` (repo root) — this experiment, end to end; `--smoke` = scratch registry.
- `game_level_predictions.csv` — 673 rows: refs, crew factor, actual/incumbent/challenger
  FT points both teams, actual + calibrated margins and totals for both models.
- `k_tuning_curve.csv` — the train-only K curve above.
- `crew_factors.csv` — per-game crew factor, listed officials, bound flags (all 1,489).
- `audits.json` — full audit detail (sampled pairs/dates, mismatch counts).
- `run_summary.json` — machine-readable everything (registration echo, reproduction
  certificates, K curve, primary verdict, secondaries, sensitivity).
- Ledger: experiments/registry.jsonl (evaluation recorded).
