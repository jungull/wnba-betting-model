# totals_online_correction_v1 — Damped Online Within-Season Bias Correction (FAIL)

*2026-07-31T00:18:59+00:00 · registered experiment `totals_online_correction_v1` (registered
2026-07-31T00:02:30.399431+00:00, regime A, primary metric `total_mae`,
incumbent `chanreval_str_total_cal`) · run mode **REAL** — recorded on the real ledger
· code `totals_online.py` (repo root) · predecessors `experiments/totals_head/REPORT.md`
(train-frozen coefficients FAIL) and `experiments/totals_groundwork/REPORT.md` §4.4
(UNdamped online correction, exploratory, pooled-negative).*

## Verdict

**FAIL.** Challenger pooled game-total MAE **14.2208** vs
incumbent **14.2236** on the identical 673 test games (pooled
improvement **+0.0029**, 90% date-clustered bootstrap CI
[-0.1065, +0.1174], 250 date clusters; team-clustered
sensitivity [-0.1022, +0.1083],
15 franchises).

| Gate (registered thresholds) | Result |
|---|---|
| 1. Pooled improvement >= 0.05 | FAIL (+0.0029) |
| 2. 90% CI excludes harm > 0.05 | FAIL (CI low -0.1065) |
| 3. No season degrades > 0.25 | PASS (worst -0.1047, 2025) |
| 4. Joint forecast: margin invariance (structural) | PASS |
| 5. Coverage unchanged | PASS (0.8617 both models) |

### Per-season game-total MAE

| Season | n | Challenger | Incumbent | Delta (+ = better) |
|---|---|---|---|---|
| 2024 | 229 | 13.1713 | 13.0680 | -0.1033 |
| 2025 | 276 | 13.4683 | 13.3637 | -0.1047 |
| 2026 | 168 | 16.8874 | 17.2116 | +0.3241 |
| pooled | 673 | 14.2208 | 14.2236 | +0.0029 |

## The mechanism (nothing fitted, nothing tuned)

**challenger(g) = str_total_cal(g) + (n/(n+15)) * mean(same-season incumbent
residuals strictly before g's date)** — K = 15 fixed a priori in the
registration; residual = total_true - str_total_cal; season openers (n = 0) get
correction = 0 exactly (registered no-info state). Same-date games never see each
other's residuals (the pool cut is strictly by DATE). Input universe: the committed
`experiments/channel_reval/predictions_v2.csv` — 673 games, seasons
2024-2026; 3 opener rows.
This script fits zero parameters: the only inputs to any challenger value are the
incumbent's own committed predictions and outcomes from strictly earlier dates.

## Seasonal bias — the registered success bar (the point of this experiment)

Preregistered bar: **max |seasonal mean bias| across test seasons < 2.5** points
(bias = mean(pred - total_true); incumbent 2026: -4.97).

| Season | n | Incumbent bias | Challenger bias | Delta abs bias (- = shrunk) | < 2.5? |
|---|---|---|---|---|---|
| 2024 | 229 | -0.0263 | -0.4579 | +0.4316 | yes |
| 2025 | 276 | +0.2790 | -0.0724 | -0.2066 | yes |
| 2026 | 168 | -4.9696 | -3.8742 | -1.0954 | NO |

**The bar is NOT MET: max |seasonal bias| = 3.8742
(challenger) vs 4.9696 (incumbent).** The 2026 bias moves
-4.9696 -> -3.8742
— about 22% of the level shift is recovered, and 1.37 points remain above the bar. The mechanism cannot reach the bar on this data — not at K=15 and not at any other damping constant: the correction is estimated from the same season's own earlier games, so it lags the level shift it chases. Observed 2026 bias across the family: -3.6861 at K=0 (the committed groundwork UNdamped reference, which was also pooled-NEGATIVE at 14.2782 MAE), -3.9955 / -3.8742 / -3.8742 at K=5/15/30, -4.9696 at K=inf (the incumbent). A bound closes the family for good: every weight n/(n+K) lies in [0, 1], so the 2026 mean correction is at most the mean positive part of the residual-pool means = 1.9844 points — best conceivable 2026 bias -2.9852, still outside the 2.5 bar, for EVERY K in [0, inf].

## Correction trace (registered secondary)

Per-game K=15 correction distribution by season (`correction_distribution.csv`):

| Season | n | zero (openers) | mean | q25 | median | q75 | max abs | mean n_prior |
|---|---|---|---|---|---|---|---|---|
| 2024 | 229 | 1 | -0.4316 | -0.4064 | +0.0287 | +0.2282 | 4.9349 | 112.9 |
| 2025 | 276 | 1 | -0.3515 | -0.6051 | -0.2340 | +0.1591 | 2.7469 | 136.3 |
| 2026 | 168 | 1 | +1.0954 | -1.3183 | +2.2508 | +3.1639 | 4.5389 | 82.3 |
| pooled | 673 | 3 | -0.0175 | -0.6027 | +0.0132 | +0.3938 | 4.9349 | 114.9 |

## K sensitivity — DIAGNOSTIC ONLY (registered as such; never used for selection)

The identical pipeline at K in {5, 15, 30}; K=15 is the registered
constant (`k_diagnostic.csv`):

| K | Pooled MAE | Pooled delta | 2024 delta | 2025 delta | 2026 delta | 2026 bias | mean abs corr |
|---|---|---|---|---|---|---|---|
| 5 | 14.2345 | -0.0108 | -0.1070 | -0.1335 | +0.3218 | -3.9955 | 1.3108 |
| 15 (registered) | 14.2208 | +0.0029 | -0.1033 | -0.1047 | +0.3241 | -3.8742 | 1.0748 |
| 30 | 14.2085 | +0.0151 | -0.0852 | -0.0809 | +0.3095 | -3.8742 | 0.8839 |

Pooled delta is monotone increasing in K over the grid (K=5: -0.0108, K=15: +0.0029, K=30: +0.0151): heavier damping (larger K, smaller corrections) tracks the incumbent more closely and bleeds less MAE in 2024/2025, while the 2026 bias recovery is nearly flat in K (spread 0.1213 points across the grid — full precision in k_diagnostic.csv). No K in the diagnostic grid comes near the registered +0.05 gate (best delta +0.0151): the FAIL is the family, not the constant. DIAGNOSTIC ONLY — nothing here was used to select anything.

## Bookie context (ungated, registered as context rows)

Consensus pre-tip totals exist for 365 of the 673 test games
(2025 from Jul 5 + 2026; **2024 has no totals lines on disk**). Bookie MAE
**14.9089** (verified vs the registered 14.909).

| Season | n | Challenger | Incumbent | Bookie | Chall - bookie | 90% CI paired delta* | Chall closer |
|---|---|---|---|---|---|---|---|
| pooled | 365 | 15.0755 | 15.2035 | 14.9089 | +0.1665 | [-0.477, +0.166] | 46.6% |
| 2025 | 197 | 13.5302 | 13.4910 | 13.2547 | +0.2756 | [-0.728, +0.199] | 42.6% |
| 2026 | 168 | 16.8874 | 17.2116 | 16.8488 | +0.0387 | [-0.450, +0.369] | 51.2% |

*delta = |bookie err| - |challenger err|, positive = challenger better; date-clustered
bootstrap (n_boot 2000, seed 20260730). Context only — never gated; no betting claim.

## Audits (all PASS — the run stops on any failure)

1. **Incumbent reproduction (registered hard assert):** pooled total MAE of the
   committed `predictions_v2.csv` = **14.223624**,
   within 1e-3 of the registered 14.2236, over exactly 673 games
   (universe asserted: row count, uniqueness, seasons, no NaN).
2. **Walk-forward residual-pool audit (registered):** 18 sampled games
   (every season opener + every season-final game + 4/season random,
   seed 20260730) — all same-season games at/after each game's date TRUNCATED, n and
   pool mean recomputed independently (plain filtering, separate code path), correction and
   challenger re-derived: identical every time (max abs diff
   8.88e-16; `residual_pool_audit.csv`). Structural asserts
   over ALL 673 games (not sampled): same-date games share
   identical pools (no same-date peeking), every season's first date has n = 0, and n_prior
   counts exactly the strictly-earlier-dated games.
3. **Margin invariance (registered, structural):** the challenger writes no margin
   column anywhere — output columns scanned for 'margin': 0;
   `predictions_v2.csv` byte-identical before/after (sha256 0afa84c83c0e...,
   match=True). The challenger shifts the TOTAL only; no margin
   forecast is produced or altered.
4. **K sensitivity (registered DIAGNOSTIC ONLY):** computed at K in {5, 30} alongside the
   registered K=15, reported above and in `k_diagnostic.csv`, and used for nothing else.
   No K was selected by any results-driven procedure in this script.

## Files

`game_level.csv` (673 rows: game_id, date, season, season_type, total_true,
incumbent, n_prior, prior_pool_mean, correction, challenger, abs errors,
bookie_consensus_total) · `bias_by_season.csv` · `k_diagnostic.csv` ·
`correction_distribution.csv` · `residual_pool_audit.csv` · `bookie_context.csv` ·
`gate_verdict.json` · `run_summary.json`.
