# totals_head_v1 — Dedicated Totals Head over the Structural Channels (FAIL)

*2026-07-30T21:45:49+00:00 · registered experiment `totals_head_v1` (registered
2026-07-30T21:23:47.159190+00:00, regime A, primary metric `total_mae`,
incumbent `chanreval_str_total_cal`) · run mode **REAL** — recorded on the real ledger
· code `totals_head.py` (repo root) · groundwork `experiments/totals_groundwork/REPORT.md`.*

## Verdict

**FAIL.** Challenger pooled game-total MAE
**14.3877** vs incumbent **14.2236** on the identical
673 test games (pooled improvement **-0.1641**, 90%
date-clustered bootstrap CI [-0.2727, -0.0572], 250 date
clusters; team-clustered sensitivity [-0.2805,
-0.0553], 15 franchises).

| Gate (registered thresholds) | Result |
|---|---|
| 1. Pooled improvement >= 0.15 | FAIL (-0.1641) |
| 2. 90% CI excludes harm > 0.08 | FAIL (CI low -0.2727) |
| 3. No season degrades > 0.25 | FAIL (worst -0.6200, 2026) |
| 4. Joint forecast: margin invariance (structural) | PASS |
| 5. Coverage unchanged | PASS (0.8617 both models) |

### Per-season game-total MAE

| Season | n | Challenger | Incumbent | Delta (+ = better) |
|---|---|---|---|---|
| 2024 | 229 | 13.1334 | 13.0680 | -0.0653 |
| 2025 | 276 | 13.3322 | 13.3637 | +0.0315 |
| 2026 | 168 | 17.8316 | 17.2116 | -0.6200 |
| pooled | 673 | 14.3877 | 14.2236 | -0.1641 |

## The fitted head

**challenger_total = a * structural_uncal_total + b + c * league_env_dev** with
**a = 0.5671, b = 71.4171, c = -0.1751**, least squares (numpy lstsq) on the
610 eligible 2021-2023 walk-forward games only
(2021-05-28 -> 2023-10-18), frozen for all test seasons —
the exact universe the incumbent's per-side calibrations were fit on.

- **Environment spec (train-only tuning):** `ewma_0.08` won the 3 inner
  walk-forward folds (evalharness.inner_tuning_splits, strictly inside 2021-2023).
  Top of the curve: ewma_0.08=13.5247, ewma_0.12=13.5258, ewma_0.2=13.5315
  (full grid: `env_tuning_curve.csv`; grid = expanding + EWMA alpha in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2]).
  league_env_dev = within-season league mean game total over STRICTLY EARLIER dates
  under that spec, minus the 2021-2023 grand mean **163.8927**
  (708 games, master_team.parquet, both season types).
- **Interpretation vs the registered expectations:** the registration expected
  a > 1 if under-dispersion is real and c > 0 if the environment tracker earns its
  slot. Fitted **a = 0.5671** — below 1 (and below the incumbent's implied ~0.650): on 2021-2023 evidence the game-to-game totals signal in the channel sum does not support expansion; the diagnosed test-era slope of 1.33 (true on calibrated pred) is carried mostly by the 2026 level shift, not by an under-used slope that a train-era fit could recover.
  Fitted **c = -0.1751** — NOT positive: the environment tracker does not earn its slot on train-era evidence.
  For scale: the incumbent's per-side calibrations imply an effective uncal-total
  slope of ~0.6500 (str_home slope 0.6765,
  str_away slope 0.6235).
- **Dispersion / bias diagnostics (test):** OLS slope of true on prediction
  1.327 (incumbent) -> 1.527 (challenger)
  (1.0 = efficient); SD(pred) 5.43 -> 4.43
  (SD true 19.36). 2026 bias (pred - true): -4.97
  (incumbent, groundwork diagnosed -4.97) -> -7.19 (challenger).

## Component attribution — what does the work

All variants least-squares-fit on the same 610 train games, frozen, scored on the 673
test games (`component_attribution.csv`):

| Variant | Pooled MAE | 2024 | 2025 | 2026 | 2026 bias |
|---|---|---|---|---|---|
| incumbent (per-side cal sum) | 14.2236 | 13.0680 | 13.3637 | 17.2116 | -4.97 |
| recal_only: a*uncal+b | 14.3146 | 13.1309 | 13.3641 | 17.4896 | -5.75 |
| env_only: b+c*env_dev | 15.0667 | 13.7742 | 13.6494 | 19.1570 | -9.22 |
| incumbent_plus_env: a*str_total_cal+b+c*env_dev | 14.3788 | 13.1312 | 13.3278 | 17.8061 | -7.18 |
| challenger: a*uncal+b+c*env_dev | 14.3877 | 13.1334 | 13.3322 | 17.8316 | -7.19 |
| posthoc_diag: incumbent + 1.0*env_dev (c:=1 a priori, NOT fitted, outside the registered family) | 14.3926 | 13.3327 | 13.7244 | 16.9354 | +4.26 |

**Attribution — the head degrades the incumbent (-0.1641 pooled) and NEITHER component earns its slot.** (1) The dedicated recalibration alone is -0.0910: a single train-fit (a, b) on the uncal channel-sum total is slightly WORSE out-of-sample than the incumbent's two per-side calibrations — the 'no dedicated totals calibration' defect was not a real defect. (2) The environment term alone (added to the untouched incumbent) is -0.1552: within 2021-2023 the environment carries no signal (corr(env_dev, total_true) = +0.019 on the 610 fit games; inner-fold c estimates flip sign fold-to-fold, and the tuner's winning spec beats the no-env reference by only +0.0083 inner MAE), so least squares freezes a near-zero, slightly NEGATIVE c that extrapolates the wrong way into the hot 2026 environment. (3) The failure is the train-frozen coefficient mechanism, not the environment signal itself: the post-hoc (unregistered, unfitted) c:=1 overlay 'incumbent + env_dev' scores 14.3926 pooled and 16.9354 on 2026 (incumbent 17.2116) — the 2026 level shift is real and env_dev points at it, but no coefficient learnable from 2021-2023 (where no such shift exists) can be trusted to apply it. A v2 should preregister an ONLINE mechanism with structure fixed a priori (e.g. same-season trailing mean-residual correction, groundwork §4.4) instead of a train-fit env coefficient.

## Bookie context (ungated, registered as context rows)

Consensus pre-tip totals exist for 365 of the 673 test games
(2025 from Jul 5 + 2026; **2024 has no totals lines on disk**). Bookie MAE
**14.9089** (verified vs the registered 14.909).

| Season | n | Challenger | Incumbent | Bookie | Chall - bookie | 90% CI paired delta* | Chall closer |
|---|---|---|---|---|---|---|---|
| pooled | 365 | 15.5126 | 15.2035 | 14.9089 | +0.6037 | [-1.034, -0.151] | 41.9% |
| 2025 | 197 | 13.5349 | 13.4910 | 13.2547 | +0.2803 | [-0.808, +0.245] | 43.7% |
| 2026 | 168 | 17.8316 | 17.2116 | 16.8488 | +0.9829 | [-1.679, -0.318] | 39.9% |

*delta = |bookie err| - |challenger err|, positive = challenger better; date-clustered
bootstrap (n_boot 2000, seed 20260730). Context only — never gated; no betting claim.

## Audits (all PASS — the run stops on any failure)

1. **Incumbent reproduction (registered hard assert):** pooled total MAE of the
   committed `predictions_v2.csv` = **14.223624**,
   within 1e-3 of the registered 14.2236. The chanreval pipeline itself was re-run
   (imported from `run_reval.py`, recorded alphas): full-frame max abs diff
   2.84e-14 over the 673 games.
2. **structural_uncal_total source (documented + verified):**
   reconstructed str_sum_h + str_sum_a from run_reval.build_features/make_games on channel_base_v2.csv with the recorded alphas (predictions_v2.csv has no uncal columns; channel_base_v2.csv holds raw ingredients only). Verified three ways: refit train-only calibrations
   equal `run_summary.json`'s recorded params to 0;
   pushing the reconstructed uncal per-side sums through the RECORDED params reproduces
   the committed `str_total_cal` to 2.84e-14;
   train universe = the recorded n = 610.
3. **Environment walk-forward audit:** 21 sampled games
   (5/test season + 2/train season,
   seed 20260730): ALL league games at/after the game date dropped, environment
   recomputed from the truncated history — identical every time (max abs diff
   0; `env_walkforward_audit.csv`).
   Neutral-filled rows (no prior same-season league game) among the 1,283 fit+test
   games: 0.
4. **Fit-window audit:** the exact 610 train games (ids + dates) are in
   `fit_window_audit.csv`; tuning folds season:2024/inner1: fit-through 2021-09-10, val 2021-09-11->2022-07-07 (140/139 games); season:2024/inner2: fit-through 2022-07-07, val 2022-07-12->2023-06-24 (279/147 games); season:2024/inner3: fit-through 2023-06-24, val 2023-06-25->2023-10-18 (426/184 games); nothing dated after
   2023-10-18 touches any fitted parameter.
5. **Margin invariance (registered gate 4, structural):** the challenger writes no
   margin column anywhere — output columns scanned for 'margin': 0;
   `predictions_v2.csv` byte-identical before/after (sha256 0afa84c83c0e...,
   match=True); reconstructed margin columns never modified
   (max abs dev vs committed: 0). The challenger
   recombines the SAME per-side predictions into a total; no margin forecast is
   produced or altered.

## Files

`game_level_totals.csv` (673 rows: game_id, date, season, season_type, total_true,
incumbent, challenger, env_dev, structural_uncal_total, contrib_recal, contrib_env,
bookie_consensus_total, abs errors) · `env_tuning_curve.csv` · `fit_window_audit.csv` ·
`env_walkforward_audit.csv` · `component_attribution.csv` · `bookie_context.csv` ·
`gate_verdict.json` · `run_summary.json`.
