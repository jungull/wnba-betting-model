# Channel Re-validation — Structural Chains vs Raw-Trend Sum on the Rebuilt Masters

*2026-07-30 · experiment `chanreval_2026_structural_repaired` (registry run 1, regime A, primary metric `margin_mae`, incumbent `raw_trend_channel_sum`) · registered 2026-07-30T17:51:46Z, before execution · data: `channel_base_v2.csv` built from `data/masters/master_team.parquet` + `master_player.parquet` (repaired 2023 paint) · code: `build_channel_base_v2.py`, `run_reval.py`, `audit_standalone.py`, `write_report.py` in this folder.*

This is the project's first registered experiment through `evalharness`: the July 2026 channel
architecture re-validated on the rebuilt uniform masters, walk-forward 2024 / 2025 / 2026, under
the preregistered standard gate (min_improvement 0.10, harm_ci_bound 0.05, per_season_tolerance
0.15, coverage_tolerance 0.0).

## Verdict

**PASS — all five gates.** Structural sum beats the raw-trend sum by
**0.630 MAE points pooled** (10.086 vs
10.716, n = 673 games), 90% date-clustered bootstrap CI
**[+0.394, +0.866]** (250 date clusters), improvement
positive in **all three test seasons**, joint forecast (home score, away score, margin, total)
improves on every component, coverage identical. The structural-chain architecture survives the
repaired data, the harness, and two new test seasons. Recorded on the ledger
(`experiments/registry.jsonl`, evaluation run 1).

## Game-level results (score-differential MAE, calibrated, walk-forward)

| Season | n games | **Structural sum** | Raw-trend sum | Naive home-adv (same games) |
|---|---|---|---|---|
| 2024 | 229 | **8.936** | 9.964 | 10.707 |
| 2025 | 276 | **10.944** | 11.378 | 12.091 |
| 2026 (thru Jul 29) | 168 | **10.244** | 10.652 | 11.246 |
| **Pooled** | 673 | **10.086** | 10.716 | 11.409 |

Frozen references (different sample — 308 games 2024 + partial 2025; pinned in
`evalharness/frozen_baselines.json`, tamper-verified at run time): incumbent structural
**9.54**, raw sum **10.53**,
home-advantage-only **11.22**.

Per-season improvement (raw − structural): 2024 **+1.028**, 2025
**+0.434**, 2026 **+0.408**. Worst season
+0.408, nowhere near the −0.15 non-inferiority floor.

### Gate detail (from `compare_to_incumbent`, ledger record)

| Gate | Threshold | Observed | Result |
|---|---|---|---|
| 1. Pooled improvement | ≥ 0.10 | +0.630 | PASS |
| 2. 90% CI excludes harm | low ≥ −0.05 | CI [+0.394, +0.866] | PASS |
| 3. Per-season non-inferiority | worst ≥ −0.15 | worst +0.408 (2026) | PASS |
| 4. Joint forecast non-degrading | each component ≤ incumbent + 0.05 | all four IMPROVE: home 8.7928 vs 9.2234, away 8.6163 vs 9.0853, margin 10.086 vs 10.7159, total 14.2236 vs 14.763 | PASS |
| 5. Coverage maintained | decline ≤ 0.0 | 0.8617 vs 0.8617 (identical eligibility rule) | PASS |

Team-clustered sensitivity CI (recorded): [+0.262,
+1.023] over 16 clusters. Footnote: the
ledger's team clustering used home-team *abbreviations*, and Phoenix is `PHO` in 2021–24 sources
but `PHX` from 2025 (documented rename), so one franchise counts as two clusters. Recomputed with
franchise `TEAM_ID` clusters (15): **[+0.291, +1.025]** — same conclusion. `run_reval.py` now
clusters by franchise ID for future runs; the primary date-clustered CI is untouched by this.

Calibration (fit on 2021–2023 eligible games only, n = 610): structural
a = 1.517, b = 0.779; raw a = 1.612,
b = 0.744; naive home margin +1.680. The structural
shrinkage slope reproduces July's 0.783 almost exactly — trend sums still overstate spread by the
same fraction on rebuilt data.

## Channel-level results (test 2024–2026 pooled, 1362 team-game rows, fallback rows excluded)

| Channel | alpha | Raw MAE | Structural MAE | Δ (str−raw) | P(structural better) | Call |
|---|---|---|---|---|---|---|
| 3pt | 0.05 | 7.237 | **7.095** | -0.142 | 98.7% | structural (confirmed) |
| FT | 0.10 | 4.364 | **4.304** | -0.060 | 95.4% | structural (confirmed) |
| Paint | 0.05 | 6.819 | **6.737** | -0.082 | 85.2% | **structural — promoted from provisional** (below) |
| Non-paint 2s | 0.05 | **3.183** | 3.289 | +0.105 | 0.0% | keep raw at channel level (unchanged) |

Per-season deltas (structural−raw): FT negative all three seasons; 3pt -0.287
(2024, P=1.000), -0.137
(2025, P=0.904), +0.045
(2026, P=0.367 — the one soft spot, 343 rows, season
in progress); paint negative all three seasons (-0.087 /
-0.056 / -0.117); np2 positive
(worse) all three seasons. Full table incl. per-season rows: `channel_results_v2.csv`.

### Paint-channel verdict: PROMOTE from provisional to structural

July's paint call was provisional *pending exactly this repair* (2023 train-season paint was
480/520 zero/NaN; July had to drop 2023 from paint training). With repaired 2023 in the training
window:

- Evidence strengthened: P(structural better) **0.760 → 0.852**
  on a test sample 2.2× larger (615 → 1,362 rows), pooled Δ −0.071 → -0.082.
- Direction is consistent in **all three** test seasons — including 2026, where the structural
  paint edge is its largest (-0.117) in a season with an elevated
  paint environment (38.9 pts/team-game vs ~35–36 prior seasons).
- The game-level sum containing structural paint passes every gate.

0.852 is still short of the ~95% standard FT/3pt clear, so paint remains the weakest structural
link — but the July condition ("re-test after 2023 repair") is satisfied, the sign held
everywhere, and no evidence emerged for demotion. Non-paint 2s stays raw at channel level
(structural hurts it in every season, as in July — the opponent multiplier amplifies noise in the
thinnest channel; np2 volume keeps shrinking: 10.4 → 5.9 pts/team-game 2021→2026); as in July, the
full-structural game-level sum still beat every variant, so the promoted joint forecast keeps all
four chains structural with np2's channel-level call recorded for the player-layer rebuild.

### Joint coherence (ROADMAP Phase 1 §3)

Channel residual covariance (structural, test rows): every off-diagonal negative — ft/3pt −4.7,
3pt/paint −20.5, paint/np2 −5.2 — the sum still benefits from error cancellation (that is why
margin MAE ≈ 10.1 while single channels err 3–7 each on ~86-pt scores). Structural covariances are
at least as negative as raw's (raw 3pt/paint −20.0, ft/paint −0.4 vs structural −2.2): the chains
do not break cancellation, they slightly deepen it. Matrices in `run_summary.json`.

## Expansion-team fallback usage: 0 game-predictions

League-prior fallback (own-tendency and allowed-side trends replaced by strictly-earlier-dates
league running means until ≥5 prior same-season games) was armed for GSV-2025, TOR-2026, PDX-2026
(first seasons only; GSV-2026 is a normal team). Actual usage:

- **15 team-rows** computed fallback
  features (5 per expansion team: 2025-GSV, 2026-PDX, 2026-TOR).
- **0 eligible game-predictions used them**: in
  the actual schedules, *every one* of those 15 games paired the expansion team with an opponent
  that also had <5 prior same-season games (opponent priors 0–4 in all 15 — expansion openers
  cluster in the season's first ~12 days). Non-expansion teams get no fallback (constitution rule
  2), so all 15 games were excluded, same as July's rule would have done.
- Excluded test games overall: 108 of
  781 (781 → 673 eligible;
  the standard early-season 5-game floor), of which those 15 involve an expansion team.

So the 2025/2026 results are **not** conditioned on any fallback prediction; the mechanism is
implemented, audited (below), and documented for seasons where an expansion team meets a
warmed-up opponent inside its first five games.

## Leakage audits (constitution rule 1 — run before believing)

1. **Shift/removal audit:** for each audited game, both team-rows' 26 input stat columns were
   blanked (the game "has not happened") and the full pipeline re-run; every feature and
   prediction on those rows must be bit-identical. **75 games audited** (60
   seeded across the three test seasons + all 15 fallback games, so
   the league-prior substitution path is itself audited): **0 mismatched
   values, max |diff| = 0.0**.
2. **Perturbation probe:** same games, stats distorted (×3 + 11) instead of blanked:
   **0 mismatches, max |diff| = 0.0** —
   no feature reads the current game's actuals.
3. Structural safeguards: every trend is `.shift(1)` before use and resets per (team, season);
   league means use strictly earlier dates only (July's certified "strict rebuild" variant,
   adopted here from the start); harness-validated splits (`walk_forward_by_season` proves
   train-max < test-min and disjointness at construction); alphas tuned via `inner_tuning_splits`
   strictly inside 2021–2023; calibration fit on 2021–2023 games only; frozen-baseline file
   tamper-check passed (8 pinned rows).

Run-1 ledger audit line shows the 60-game version (0 fallback games existed among *eligible*
games); the extended 75-game audit is `audit_standalone.py` → `audit_extended.json`, and
`run_reval.py` now includes fallback games automatically.

## Honest comparison to the July numbers

- **Does structural still beat raw?** Yes — pooled +0.630 here vs July's
  +0.99 (n=308). The margin is smaller because 2025/2026 are harder seasons for both models (and
  July's 2025 was a 79-game partial); like-for-like 2024 shows +1.028,
  matching July's 2024 gap (8.97 vs 10.02).
- **Is 2024 consistent with the frozen 9.54?** Yes. The frozen 9.54 is pooled over 2024 +
  partial-2025. July's own 2024-only figure was **8.97**; this rerun's 2024 is
  **8.936** on 229 games — a 0.03 match on rebuilt
  data, repaired 2023 training, harness-tuned alphas, and slightly different calibration sample.
  The pooled 10.086 here is not comparable to 9.54 (different season mix:
  full 2025 + in-progress 2026, both higher-MAE seasons for every model including naive).
- **Did repaired 2023 change paint-channel quality?** Yes, modestly and in the right direction —
  see the paint verdict above (P 0.760 → 0.852, negative delta in all three seasons). The repair
  also grew the calibration/tuning base to all of 2021–2023 (610 train games).
- Alphas: low alphas win again (rule 3). ft moved 0.08 → 0.10 (inner-fold curve is nearly flat
  between them: 4.3310 vs 4.3304), np2 0.10 → 0.05; 3pt and paint unchanged at 0.05.
- 2026 note: scoring environment is up (FT 16.7, paint 38.9 per team-game); the 3pt structural
  edge has not yet appeared in 2026 (channel Δ +0.045,
  P=0.367, 343 rows) while paint's is strongest
  there. Worth rechecking at season close — no action now, the game-level gate holds in 2026
  (+0.408).

## Methodology deviations from July (all preregistered or forced, none post-hoc)

1. Paint & np2 train on 2021–2023 (July: 2021–2022; 2023 was corrupted) — the registered purpose
   of the rerun.
2. Alpha tuning through `evalharness.inner_tuning_splits` (3 walk-forward folds inside 2021–2023)
   instead of July's pooled train-window MAE. Never touches test.
3. League means strictly-earlier-dates from the start (July's final certified variant; its 9.54
   was produced under exactly this rule).
4. Test = full 2024, full 2025, 2026 through Jul 29, split via `walk_forward_by_season`; all
   fitted parameters (alphas, calibrations) come from the season-2024 split's train window =
   2021–2023 only and are applied unchanged to 2025/2026 (stricter than expanding-window refits).
5. Expansion-team league-prior fallback implemented + audited (used by 0 eligible games this run).
6. Only the registered pair (structural vs raw sum) plus the naive context model was evaluated;
   July's exploratory monolithic-ridge/hybrid variants were not re-run — unregistered results are
   void, and the registered hypothesis is the sum-vs-sum comparison.

## Data notes

- `channel_base_v2.csv`: 2,978 team-game rows / 1,489 games, 2021 – Jul 29 2026. Box identity
  (ch_ft + ch_3pt + 2·(fgm−fg3m) = pts): **0 violations**; ch_np2 < 0: **0**; player-summed paint
  = master team paint on **every** row; opp-mirror consistency **0** disagreements.
- **Invariance to the pending team-gamelog upgrade:** master_team currently derives 1,296 team
  rows (2021–23 regular seasons) from player sums. The channel inputs used here — ftm, fg3m, fgm,
  pts — are *identical* between derived and real team rows (player-sum reconciliation 0-mismatch;
  ftm/fg3m/fgm/pts all 2,132/2,132 exact vs the July-15 Drive masters). Tonight's real-team-gamelog
  upgrade changes team-credited turnovers only; **these results are invariant to it.**

## Files

- `build_channel_base_v2.py` → `channel_base_v2.csv` (rebuilds + re-proves identities every run)
- `run_reval.py` → `channel_results_v2.csv`, `game_level_results_v2.csv`, `predictions_v2.csv`
  (673 per-game rows, both models + naive, calibrated + uncalibrated), `run_summary.json`
  (alphas, folds, calibrations, covariance, fallback accounting, gate verdict)
- `audit_standalone.py` → `audit_extended.json` (75-game removal + perturbation audit)
- `write_report.py` → this report (regenerates from the artifacts above)
- Ledger: `experiments/registry.jsonl` — evaluation run 1 recorded with the full verdict.
  Leaderboards deliberately **not** rendered by this run.
